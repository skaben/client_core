import os
import time
import pygame as pg
import pygame.mixer as mixer


class SoundLoader:

    """ Sound configurator """

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
        try:
            self.channels.get(channel).play(self.sound.get(sound), **kwargs)
        except Exception:
            raise

    def stop(self, channel):
        try:
            ch = self.channels.get(channel)
            if ch.get_busy():
                ch.stop()
        except Exception:
            raise

    def fadeout(self, fadeout_time, channels=None):
        if not channels:
            mixer = list(self.channels.values())
        elif isinstance(channels, str):
            mixer = (channels,)
        else:
            mixer = list(channels)
        try:
            for ch in mixer:
                ch.fadeout(fadeout_time)
        except Exception:
            raise

    def _snd(fname, volume=None):
        if not volume:
            volume = 1

        try:
            snd = mixer.Sound(file=fname)
            snd.set_volume(volume)
            return snd
        except FileNotFoundError:
            raise FileNotFoundError(f'failed to load sound: {fname}')


class ImageLoader:

    """ Image Loader class """

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
