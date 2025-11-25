import os

def abs_path(path):
    BASE = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(BASE, path)
    return os.path.abspath(path)