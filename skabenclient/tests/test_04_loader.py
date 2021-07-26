import os
import shutil

import pygame as pg
import pytest

import skabenclient.tests.mock.mixer as mock_mixer
from skabenclient.loaders import SoundLoader

root_dir = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def create_test_sounds():
    path = "/tmp/skaben/sound_dir"
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    res_snd = os.path.join(root_dir, "res/snd.ogg")
    for x in range(3):
        shutil.copyfile(res_snd, f"{path}/snd_{x}.ogg")

    fnames = []
    for r, d, f in os.walk(path):
        for filename in f:
            fnames.append(filename)

    return {
        "root": path,
        "files": fnames
    }


def test_sound_loader_file(create_test_sounds, monkeypatch):
    snd = create_test_sounds
    channel_list = ['bg', 'fg', 'fx']
    monkeypatch.setattr(pg.mixer, "init", mock_mixer.init)
    monkeypatch.setattr(pg.mixer, "Sound", mock_mixer.sound)
    monkeypatch.setattr(pg.mixer, "Channel", mock_mixer.channel)
    loader = SoundLoader(snd['root'], channel_list)

    assert list(loader.sound) == [fn.split(".")[0] for fn in snd['files']], \
        'missing sound files in loader'
