bind = "0.0.0.0:8080"
workers = 1          # Single worker - Pi 4 memory constraint
threads = 2          # Threads for concurrent API requests
timeout = 120
preload_app = False  # False pour que le thread poller survive après fork()
accesslog = "-"
errorlog = "-"
loglevel = "info"
