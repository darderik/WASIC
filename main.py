from threading import Thread
from connections import Connections
from webApp.webapp import WebApp

# Global variables


def main():
    # Init connection class
    Connections.fetchInstruments()

    


if __name__ == "__main__":
    main()
