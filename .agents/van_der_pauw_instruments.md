# Note per agenti: strumenti e task van der Pauw

Aggiornato il 12 ottobre 2026. Queste note documentano il codice locale e le decisioni dell'utente; non sostituiscono i manuali degli strumenti. Consultarle prima di modificare la task, i driver o le relative diagnosi.

## Modelli e fonti

La task attuale usa il nanovoltmetro Keithley 2182 / 2182A (`keithley2182`) e la sorgente di corrente Keithley 6221 (`keithley6221`), oltre alla Relay Matrix. Il riferimento dell'utente a «NV2182 e SM2401» non cambia questa associazione: il codice esaminato non dimostra il comportamento di un modello 2401. Non trasferire registri di stato, comandi o limiti del 6221 a un altro modello senza verificarli.

Fonti locali:

- `addons/tasks/van_der_pauw.py`: configurazione, commutazione, acquisizione e cleanup.
- `addons/instruments/keithley2182.py` e `keithley6221.py`: registrazione dei driver PyMeasure.
- `addons/instruments/RelayMatrix.py`: protocollo e commutazione della matrice.
- `tests/test_van_der_pauw.py`: scenari attesi con strumenti simulati.
- `tests/diagnose_vdp_hardware.py`: script di diagnosi hardware, distinto dalla task.

## Sorgente: output continuo durante l'acquisizione

Decisione esplicita dell'utente: evitare spegnimenti e riaccensioni ripetuti dell'output, anche per limitare l'usura del relè di uscita. La motivazione sull'usura è una preferenza operativa comunicata dall'utente; il codice non verifica la costruzione interna o la durata del relè del singolo modello.

- Configurare la sorgente a output disabilitato: reset, corrente iniziale zero, compliance, autorange e LO non collegato a terra (`output_low_grounded = False`). Non cambiare il riferimento LO senza riesaminare il cablaggio.
- Dopo la configurazione degli strumenti, impostare la corrente positiva e abilitare l'output una volta.
- Lasciare l'output attivo durante inversioni di corrente, passaggi RA/RB, attese tra ripetizioni e cicli scartati per sola compliance. Cambiare direttamente `source_current` tra +I e -I; non aggiungere OFF/ON o azzeramenti a ogni misura.
- Durante l'apertura del percorso di corrente è accettata la compliance transitoria. Non leggerla per decidere la validità del ciclo mentre i relè sono aperti.
- Sequenza della task: aprire tutti i relè, attendere `relay_settle_s`, chiudere il nuovo percorso, attendere `relay_settle_s`, impostare la polarità, attendere `current_settle_s`, poi controllare lo stato e acquisire. La matrice viene quindi commutata con sorgente attiva.
- L'output rimane attivo anche durante `repeat_delay_s`; alla fine di una misura la corrente resta negativa fino alla successiva impostazione.
- Inizializzazione e cleanup possono disabilitare l'output: la regola riguarda le commutazioni ripetute durante l'acquisizione.

## Compliance e stato del 6221

La task configura `:FORM:SREG ASC` e legge il registro di condizione corrente con `:STAT:MEAS:COND?`, prima e dopo ogni lettura di tensione. Non usare un evento memorizzato durante l'apertura dei relè come prova di compliance ancora presente dopo la richiusura.

Mappatura adottata nel codice, con riferimento nel commento al manuale 622x, sezione 11:

| Maschera | Interpretazione nella task | Comportamento |
| --- | --- | --- |
| `0x1` | Reading overflow | Interrompere la task |
| `0x2` | Interlock asserted, output consentito | Non trattarlo come guasto |
| `0x4` | Sovratemperatura | Interrompere la task |
| `0x8` | Compliance di tensione | Scartare il ciclo se non ci sono anche i guasti `0x1` / `0x4` |

Se la compliance persiste al momento delle letture, scartare l'intera coppia RA/RB e non pubblicare Rs, anche se RA era già completa. Annotare il motivo nei dati grezzi e proseguire con la ripetizione successiva mantenendo l'output attivo. La task non ritenta la compliance con un'attesa aggiuntiva: l'attesa avviene prima del controllo.

Il messaggio diagnostico include corrente richiesta, limite di tensione e percorso relè. `compliance_V / abs(current_A)` è il limite resistivo indicativo dell'intero percorso di corrente, inclusi contatti e cablaggio, non la resistenza di foglio. Per compliance persistente controllare gruppi HI/LO, collegamenti e contatti, quindi valutare corrente e limite di tensione.

## Nanovoltmetro 2182 / 2182A

- Dopo il reset inviare `:INIT:CONT OFF` e `:ABOR` prima di `*OPC?`: il codice segnala che una query OPC con acquisizione continua può bloccare il 2182.
- `*OPC?` conferma il completamento dei comandi e deve restituire `1`. Non sostituisce l'assestamento analogico dopo commutazioni o inversioni.
- La misura usa canale 1, funzione tensione, `voltage_nplc`, autozero attivo e offset del canale disabilitato.
- `voltage_range_V = 0` seleziona autorange; un valore diverso seleziona una portata fissa. Conservare entrambe le possibilità per valutare stabilità e overrange.
- Configurare trigger immediato, `trigger_count = 1` e `:SAMP:COUN 1`; verificare nuovamente OPC e gli errori di configurazione prima di abilitare la sorgente.
- Non accettare NaN, infinito o valori con modulo almeno `1e30`: quest'ultima soglia è il criterio adottato dalla task per riconoscere letture di overrange.
- Ritentare soltanto letture esplicitamente invalide, mantenendo percorso e polarità. Numero massimo di tentativi: `overrange_retries + 1`, con `overrange_retry_delay_s` tra i tentativi. Annotare polarità, campione, tentativo e valore invalido nei raw.
- Un timeout o un errore di trasporto deve interrompere la task e passare al cleanup; non mascherarlo come overrange e non ripetere automaticamente comandi con esito incerto.

## Dimensionamento e trattamento delle misure

Default attuali: `current_A = 100 µA`, `compliance_V = 1 V`, `nplc = 5`, un campione per polarità, `relay_settle_s = 0.1 s`, `current_settle_s = 0.2 s`, tre retry di overrange distanziati di `0.5 s`. Sono impostazioni iniziali del software, non tempi o valori ottimali dimostrati per ogni campione.

- Distinguere il tempo meccanico/di commutazione (`relay_settle_s`), l'assestamento dopo cambio corrente (`current_settle_s`) e l'integrazione del meter (`nplc`). Non eliminare le attese perché OPC risponde subito.
- La task stima ogni resistenza con `abs(media(V+) - media(V-)) / (2 * I)`: l'inversione cancella un offset additivo stabile tra le due polarità. L'uso del modulo è la convenzione attuale, non una verifica della correttezza del cablaggio.
- I contatti 1..4 sono ordinati lungo il perimetro. Le configurazioni sono RA = V43/I12 e RB = V14/I23. I quattro gruppi di relè devono essere lettere distinte e i quattro indici di contatto distinti; validarli prima di toccare l'hardware.
- Rs risolve `exp(-pi*RA/Rs) + exp(-pi*RB/Rs) = 1`, in ohm/quadro. Non confondere Rs con resistività volumica: la task non usa uno spessore.
- Il solver richiede RA/RB finite e positive; usa normalizzazione e `expm1` per mantenere precisione anche con scale molto piccole o resistenze asimmetriche.
- Pubblicare RA, RB e Rs soltanto dopo un ciclo completo valido. Conservare i raw anche per acquisizioni parziali, stop, errori e compliance; non trasformarli in valori elaborati validi.

## Matrice, cancellazione e cleanup

- Il driver della Relay Matrix consuma l'`OK` di ogni comando; le query consumano sia risposta sia `OK`. Le operazioni di commutazione verificano anche OPC. Non inviare il comando successivo lasciando risposte pendenti.
- Dopo perdita dell'handshake il driver rifiuta altri comandi fino alla riconnessione. Non introdurre retry ciechi sulla stessa sessione.
- Le attese della task usano `exit_flag.wait(...)` e sono interrompibili, anche durante l'assestamento e i retry.
- Il cleanup nel `finally` disabilita l'output, tenta di azzerare la corrente, attende e apre la matrice. L'attesa finale usa `sleep` perché deve avvenire anche con stop già richiesto.
- Se il comando di disabilitazione fallisce, il cleanup non apre la matrice: conserva lo stato dei relè e segnala il fallimento. Questo comportamento finale è distinto dalle commutazioni previste durante l'acquisizione.

## Verifica e limiti delle evidenze

I test simulati documentano output continuo, commutazione, attese, inversioni, letture invalide, compliance e cleanup. Non provano usura dei relè, tempi reali di recupero dalla compliance o assestamento del campione. Nel controllo di questa sessione i test completi sono stati saltati per dipendenze mancanti; è passato un controllo isolato del flusso con strumenti simulati.

Lo script `tests/diagnose_vdp_hardware.py` contiene ancora OFF/ON nei cicli attivi: non copiarne quella sequenza nella task come se fosse la politica aggiornata. È uno strumento diagnostico separato; non eseguirlo automaticamente leggendo queste note e non usare simultaneamente task e diagnosi sulle stesse connessioni.
