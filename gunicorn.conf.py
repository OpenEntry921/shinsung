def post_worker_init(worker):
    from app.sms import start_worker
    start_worker(worker.wsgi)
