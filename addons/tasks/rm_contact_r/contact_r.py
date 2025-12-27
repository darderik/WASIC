from typing import Optional, cast
import time
import logging
from tasks import Task, Tasks, ChartData, ChartData_Config
from instruments import Instrument_Entry
from addons.instruments import RelayMatrix, SM2401
from connections import Connections


def measure_contact_r(task_obj: Task) -> None:
	"""Measure 4‑wire contact resistance at a given position using SM2401 + relay matrix.

	Reproducibility: before every reading we hard reset the relay matrix routing
	and then apply the requested 4‑wire route (e.g., "A1"). This ensures no
	residual paths from previous measurements. The SM2401 is configured in
	4‑wire resistance (FRES) mode, which enables Kelvin sensing (RSEN ON),
	sources the test current internally, and returns V, I, R.
	"""
	logger = logging.getLogger(__name__)
	data = task_obj.data
	exit_flag = task_obj.exit_flag

	# Instruments
	rm_entry: Optional[Instrument_Entry] = Connections().get_instrument("Relay Matrix")
	sm_entry: Optional[Instrument_Entry] = (
		Connections().get_instrument("Model 2401")
		or Connections().get_instrument("SM2401")
	)
	if rm_entry is None or sm_entry is None:
		logger.error("Missing instruments: need 'Relay Matrix' and 'Model 2401' (SM2401).")
		return

	rm: RelayMatrix = cast(RelayMatrix, rm_entry.scpi_instrument)
	sm: SM2401 = cast(SM2401, sm_entry.scpi_instrument)

	# Parameters
	sample_count = int(task_obj.parameters.get("sample_count", "10"))
	settle_time_s = float(task_obj.parameters.get("settle_time_s", "0.2"))
	nplc = float(task_obj.parameters.get("nplc", "1.0"))
	ohm_range = float(task_obj.parameters.get("range", "-1"))  # <0 => autorange
	contact_matrix = str(task_obj.parameters.get("contact_matrix", "A1"))
	# Chart setup (labels = sample index, values = resistance in ohm)
	chart = ChartData(
		name="Contact R (SM2401 @ A1)",
		config=ChartData_Config(
			pop_raw=False,
			include_raw_on_save=True,
			atomic_save=True,
			custom_type="scatter",
			refresh_all=False,
		),
		math_formula_y=lambda v: float(v),  # identity; raw already ohms
	)
	chart.x_series.meta.label = "Sample"
	chart.x_series.meta.unit = "#"
	chart.y_series.meta.label = "Resistance"
	chart.y_series.meta.unit = "ohm"

	chart.x_series.raw = []
	chart.y_series.raw = []
	data.append(chart)

	# Configure SMU once: 4W resistance mode (Kelvin), autorange if range<0, NPLC for stability
	try:
		rng = 0 if ohm_range < 0 else ohm_range
		sm.configure_fres_measure(range=rng, nplc=nplc, offset_comp=True)
		sm.output_on()
	except Exception as e:
		logger.warning(f"SM2401 configuration warning: {e}")

	def route_4w_to_position() -> None:
		# Single routing token expected to map the 4‑wire bundle (e.g., "A1")
		# If your matrix requires explicit A/B/C/D lines, adapt here accordingly.
		rm.switch_commute(contact_matrix)

	try:
		for i in range(sample_count):
			if exit_flag.is_set():
				logger.info("Exit flag set; terminating contact R task.")
				break
			# Reset then set routes for every reading to ensure reproducibility
			rm.switch_commute_reset(contact_matrix)
			rm.opc()
			route_4w_to_position()
			rm.opc()
			time.sleep(settle_time_s)
			# Measure
			try:
				v_i_r = sm.read_fres()  # [V, I, R]
				r = float(v_i_r[2]) if v_i_r else float('nan')
			except Exception as e:
				logger.error(f"SM2401 measurement failed: {e}")
				r = float('nan')
			chart.x_series.raw.append(i)
			chart.y_series.raw.append(r)
	except Exception as e:
		logger.error(f"Error in contact R task: {e}")
	finally:
		try:
			sm.output_off()
		except Exception:
			pass
		try:
			rm.switch_commute_reset_all()
		except Exception:
			pass
		exit_flag.set()


def init_contact_r_task() -> None:
	t = Task(
		name="Contact R (SM2401 @ A1)",
		description="Measures 4-wire contact resistance at A1 with SM2401; resets relays before each reading.",
		instrs_aliases=["Relay Matrix", "Model 2401"],
		function=measure_contact_r,
		parameters={
			"sample_count": "10",
			"settle_time_s": "0.2",
			"nplc": "1.0",
			"range": "-1",
			"contact_matrix":"A1",
		},
	)
	Tasks().add_task(t)