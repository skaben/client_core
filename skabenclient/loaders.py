import os
import time
import yaml
import logging
import pygame as pg
import pygame.mixer as mixer


def get_yaml_loader():

    class Loader(yaml.SafeLoader):
        """ Yaml Loader extended """
        def construct_python_tuple(self, node):
            return tuple(self.construct_sequence(node))

    Loader.add_constructor(
        'tag:yaml.org,2002:python/tuple',
        Loader.construct_python_tuple)

    return Loader


class SoundLoader:

    """ Sound loader

        Loads .ogg files from directory, set multiple sound channels by channel list,
        provide play stop fade operations for loaded sounds
     """

    enabled = None

    def __init__(self, sound_dir, channel_list=None):
        if not channel_list:
            channel_list = ['bg', 'fg', 'fx']
        self.sound = {}
        self.channels = {}
        try:
            mixer.init()
            time.sleep(.2)
            self.enabled = True
        except Exception:
            raise

        for r, d, f in os.walk(sound_dir):
            for filename in f:
                fpath = os.path.join(r, filename)
                self.sound[filename.split('.')[0]] = self._snd(fpath)

        # TODO: check for maximum number of channels available
        for idx, ch in enumerate(channel_list, 1):
            self.channels[ch] = mixer.Channel(idx)

    def play(self, sound, channel, **kwargs):
        """ Plays sound by selected channel """
        if not self.enabled:
            # stays silent
            return
        sound_file = self.sound.get(sound)
        if not sound_file:
            logging.error(f'{sound_file} not found in {self.sound}')
        try:
            delay = kwargs.get('delay')
            # compatibility with pygame.mixer.Sound named arguments
            sound_kwargs = {k: kwargs.get(k) for k in kwargs
                            if k in ['loops', 'maxtime', 'fade_ms']}
            if delay:
                time.sleep(delay)
            self.channels.get(channel).play(self.sound.get(sound), **sound_kwargs)
        except Exception:
            raise

    def stop(self, channel):
        """ Stops all sound in selected channel """
        try:
            ch = self.channels.get(channel)
            if ch.get_busy():
                ch.stop()
        except Exception:
            raise

    def fadeout(self, fadeout_time, channels=None):
        """ Fade out sound in selected channel list, or all"""
        mixer = list()
        if not channels:
            mixer = list(self.channels.values())
        elif isinstance(channels, (int, str)):
            mixer.append(str(channels))
        else:
            mixer.extend(channels)
        try:
            for ch in mixer:
                self.channels[ch].fadeout(fadeout_time)
        except Exception:
            raise

    def mute(self, channel, mute=True):
        """ Mute selected channel """
        if mute:
            self.channels.get(channel).set_volume(0)
        else:
            self.channels.get(channel).set_volume(1)

    def _snd(self, fname, volume=None):
        """ Loads sound from .ogg to pygame mixer.Sound object """
        if not volume:
            volume = 1

        try:
            snd = mixer.Sound(file=fname)
            snd.set_volume(volume)
            return snd
        except FileNotFoundError:
            raise FileNotFoundError(f'failed to load sound: {fname}')
        except Exception:
            raise Exception


class ImageLoader:

    """ Image Loader class

        Loads images from directories, scaling images, provide pygame image objects.
    """

    def __init__(self, image_dir):
        self.images = {}
        for r, d, f in os.walk(image_dir):
            f.sort()
            for filename in f:
                self.images.update({filename: pg.image.load(filename).convert()})

    def scale_image_constrain(self, img, w, h):
        """ Scale image constrain proportions """
        _o = img.get_rect()
        if _o.width > _o.height:
            if w > _o.width:
                percent = round(w / _o.width, 2)
                img = pg.transform.scale(img, (int(_o.width / percent), int(_o.height / percent)))
            else:
                percent = round(_o.width / w, 2)
                img = pg.transform.scale(img, (int(_o.width * percent), int(_o.height * percent)))
        else:
            if h > _o.height:
                percent = round(h / _o.height, 2)
                img = pg.transform.scale(img, (int(_o.width * percent), int(_o.height * percent)))
            else:
                percent = round(_o.height / h, 2)
                img = pg.transform.scale(img, (int(_o.width / percent), int(_o.height / percent)))
        return img

    def scale_image(self, img, w, h):
        """ Scale image fit to screen """
        _o = img.get_rect()
        if _o.height > _o.width:
            percent = round(w / _o.width, 2)
            img = pg.transform.scale(img, (int(_o.width * percent), h))
        else:
            percent = round(h / _o.height, 2)
            img = pg.transform.scale(img, (w, int(_o.height * percent)))
        return img
