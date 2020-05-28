class Sound:

    """ sound mock class """ 

    def __init__(self, file_name):
        self.file_name = file_name

    def set_volume(self, val):
        return f"set volume to {val}"
        

def init():
    """ pygame mixer mock init """
    return "mocking pygame mixer init"

def sound(file):
    """ pygame mixer Sound mock """
    return Sound(file)       

def channel(idx):
    return idx
