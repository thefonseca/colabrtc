import os
import glob
import time


import imageio
import numpy as np
from skimage.transform import resize
import cv2
import fire

import torch
import sys
sys.path.insert(0, "/content/avatarify")
sys.path.insert(0, "/content/avatarify/fomm")

from animate import normalize_kp
from cam_fomm import (load_checkpoints, normalize_alignment_kp, 
                                get_frame_kp, is_new_frame_better, crop,
                                pad_img, load_stylegan_avatar, log)

import face_alignment

from peer import FrameTransformer
from call import ColabCall


def predict(driving_frame, source_image, relative, adapt_movement_scale, fa, 
            generator, kp_detector, kp_driving_initial, device='cuda'):
    global start_frame
    global start_frame_kp
    #global kp_driving_initial

    with torch.no_grad():
        source = torch.tensor(source_image[np.newaxis].astype(np.float32)).permute(0, 3, 1, 2).to(device)
        driving = torch.tensor(driving_frame[np.newaxis].astype(np.float32)).permute(0, 3, 1, 2).to(device)
        kp_source = kp_detector(source)

        if kp_driving_initial is None:
            kp_driving_initial = kp_detector(driving)
            start_frame = driving_frame.copy()
            start_frame_kp = get_frame_kp(fa, driving_frame)

        kp_driving = kp_detector(driving)
        kp_norm = normalize_kp(kp_source=kp_source, kp_driving=kp_driving,
                            kp_driving_initial=kp_driving_initial, use_relative_movement=relative,
                            use_relative_jacobian=relative, adapt_movement_scale=adapt_movement_scale)
        out = generator(source, kp_source=kp_source, kp_driving=kp_norm)

        out = np.transpose(out['prediction'].data.cpu().numpy(), [0, 2, 3, 1])[0]
        out = (np.clip(out, 0, 1) * 255).astype(np.uint8)

        return out


def change_avatar(fa, new_avatar):
    # global avatar, avatar_kp
    avatar_kp = get_frame_kp(fa, new_avatar)
    avatar = new_avatar
    return avatar, avatar_kp


def load_avatars(avatars_dir='./avatarify/avatars'):
    avatars=[]
    images_list = sorted(glob.glob(f'{avatars_dir}/*'))
    for i, f in enumerate(images_list):
        if f.endswith('.jpg') or f.endswith('.jpeg') or f.endswith('.png'):
            log(f'{i}: {f}')
            img = imageio.imread(f)
            if img.ndim == 2:
                img = np.tile(img[..., None], [1, 1, 3])
            img = resize(img, (256, 256))[..., :3]
            avatars.append(img)
    return avatars


def generate_fake_frame(frame, avatar, generator, kp_detector, relative=False, adapt_scale=True, 
                        no_pad=False, verbose=False, device='cuda', 
                        passthrough=False, kp_driving_initial=None, 
                        show_fps=False):

    fa = face_alignment.FaceAlignment(face_alignment.LandmarksType._2D, flip_input=True, device=device)
    avatar, avatar_kp = change_avatar(fa, avatar)

    frame_proportion = 0.9
    overlay_alpha = 0.0
    preview_flip = False
    output_flip = False
    find_keyframe = False

    fps_hist = []
    fps = 0

    t_start = time.time()

    green_overlay = False
    frame_orig = frame.copy()

    frame, lrud = crop(frame, p=frame_proportion)
    frame = resize(frame, (256, 256))[..., :3]

    if find_keyframe:
        if is_new_frame_better(fa, avatar, frame, device):
            log("Taking new frame!")
            green_overlay = True
            kp_driving_initial = None

    if verbose:
        preproc_time = (time.time() - t_start) * 1000
        log(f'PREPROC: {preproc_time:.3f}ms')

    if passthrough:
        out = frame_orig[..., ::-1]
    else:
        pred_start = time.time()
        pred = predict(frame, avatar, relative, adapt_scale, fa, generator, kp_detector, kp_driving_initial, device=device)
        out = pred
        pred_time = (time.time() - pred_start) * 1000
        if verbose:
            log(f'PRED: {pred_time:.3f}ms')

    postproc_start = time.time()

    if not no_pad:
        out = pad_img(out, frame_orig)

    if out.dtype != np.uint8:
        out = (out * 255).astype(np.uint8)
    
    # elif key == ord('w'):
    #     frame_proportion -= 0.05
    #     frame_proportion = max(frame_proportion, 0.1)
    # elif key == ord('s'):
    #     frame_proportion += 0.05
    #     frame_proportion = min(frame_proportion, 1.0)
    # elif key == ord('x'):
    #     kp_driving_initial = None
    # elif key == ord('z'):
    #     overlay_alpha = max(overlay_alpha - 0.1, 0.0)
    # elif key == ord('c'):
    #     overlay_alpha = min(overlay_alpha + 0.1, 1.0)
    # elif key == ord('r'):
    #     preview_flip = not preview_flip
    # elif key == ord('t'):
    #     output_flip = not output_flip
    # elif key == ord('f'):
    #     find_keyframe = not find_keyframe
    # elif key == ord('q'):
    #     try:
    #         log('Loading StyleGAN avatar...')
    #         avatar = load_stylegan_avatar()
    #         passthrough = False
    #         change_avatar(fa, avatar)
    #     except:
    #         log('Failed to load StyleGAN avatar')
    # elif key == ord('i'):
    #     show_fps = not show_fps
    # elif key == 48:
    #     passthrough = not passthrough
    # elif key != -1:
    #     log(key)
    
    preview_frame = cv2.addWeighted(avatar[:,:,::-1], overlay_alpha, frame, 1.0 - overlay_alpha, 0.0)
    
    if preview_flip:
        preview_frame = cv2.flip(preview_frame, 1)
        
    if output_flip:
        out = cv2.flip(out, 1)
        
    if green_overlay:
        green_alpha = 0.8
        overlay = preview_frame.copy()
        overlay[:] = (0, 255, 0)
        preview_frame = cv2.addWeighted( preview_frame, green_alpha, overlay, 1.0 - green_alpha, 0.0)
        
    if find_keyframe:
        preview_frame = cv2.putText(preview_frame, display_string, (10, 220), 0, 0.5, (255, 255, 255), 1)

    if show_fps:
        fps_string = f'FPS: {fps:.2f}'
        preview_frame = cv2.putText(preview_frame, fps_string, (10, 240), 0, 0.5, (255, 255, 255), 1)
        frame = cv2.putText(frame, fps_string, (10, 240), 0, 0.5, (255, 255, 255), 1)
        
    if verbose:
        postproc_time = (time.time() - postproc_start) * 1000
        log(f'POSTPROC: {postproc_time:.3f}ms')
        log(f'FPS: {fps:.2f}')

    fps_hist.append(time.time() - t_start)
    if len(fps_hist) == 10:
        fps = 10 / sum(fps_hist)
        fps_hist = []
    
    return preview_frame, out[..., ::-1], kp_driving_initial


class Avatarify(FrameTransformer):
    global kp_driving_initial
    kp_driving_initial = None

    def __init__(self, freq=1./30):
        import torch
        self.config = '/content/avatarify/fomm/config/vox-adv-256.yaml'
        self.checkpoint = '/content/avatarify/vox-adv-cpk.pth.tar'
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.avatar = 0
        self.freq = freq

    def setup(self):
        from avatarify_colab import load_checkpoints, generate_fake_frame, load_avatars
        import traceback
        import cv2

        self.load_checkpoints = load_checkpoints
        self.generate_fake_frame = generate_fake_frame
        self.load_avatars = load_avatars
        self.traceback = traceback
        self.cv2 = cv2
        generator, kp_detector = load_checkpoints(config_path=self.config, 
                                                  checkpoint_path=self.checkpoint, 
                                                  device=self.device)
        self.generator = generator
        self.kp_detector = kp_detector
        self.avatars = load_avatars()

        import numpy as np
        test_frame = np.zeros((200, 200, 3))
        self.generate_fake_frame(test_frame, self.avatars[self.avatar], 
                                 self.generator, self.kp_detector,
                                 kp_driving_initial=kp_driving_initial,
                                 verbose=True)
    
    def transform(self, frame, frame_idx=None, avatar=0):
        if frame_idx % int(1./self.freq) != 0:
            return

        try:
            global display_string
            display_string = ""
            global kp_driving_initial

            frame = self.cv2.resize(frame, (0,0), fx=0.5, fy=0.5) 
            # Call avatarify models here
            (preview_frame, fake_frame, 
            kp_driving_initial) = self.generate_fake_frame(frame, 
                                                           self.avatars[self.avatar], 
                                                           self.generator, 
                                                           self.kp_detector,
                                                           kp_driving_initial=kp_driving_initial,
                                                           verbose=True)
            #fake_frame = self.cv2.resize(fake_frame, (0,0), fx=2., fy=2.) 
            return fake_frame
        except Exception as err:
            self.traceback.print_exc()
            return frame

def run(room=None, signaling_folder='/content/webrtc', frame_freq=1./30, verbose=False):
    if room:
        room = str(room)
        
    afy = Avatarify(freq=frame_freq)
    call = ColabCall()
    call.create(room, signaling_folder=signaling_folder, verbose=verbose,
                frame_transformer=afy, multiprocess=False)

if __name__ == '__main__':
    fire.Fire(run)