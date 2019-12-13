import os
import shutil
import pytest
from skabenclient.loaders import SoundLoader


@pytest.fixture
def create_test_sounds():
    path = "/tmp/skaben/sound_dir"
    os.makedirs(path)
    for x in range(3):
        shutil.copyfile("tests/res/snd.ogg", f"{path}/snd_{x}.ogg")

