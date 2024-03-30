import time


class Timer:
    def __enter__(self):
        self.start_time = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.end_time = time.monotonic()

    def get_time(self):
        return self.end_time - self.start_time
