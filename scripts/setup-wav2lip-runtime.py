#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "workspace" / "runtimes" / "Wav2Lip"
DEFAULT_CHECKPOINT_PATH = PROJECT_ROOT / "model" / "wav2lip" / "checkpoints" / "wav2lip_gan.pth"
WAV2LIP_REPO = "https://github.com/Rudrabha/Wav2Lip.git"
WAV2LIP_CHECKPOINT_DRIVE_ID = "15G3U08c8xsCkOqQxE38Z2XXDnPcOptNk"
S3FD_URL = "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth"


def run(command, cwd=None):
    print("+", " ".join(str(part) for part in command))
    result = subprocess.run(command, cwd=cwd, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def is_ready_file(path: Path, min_size: int) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size >= min_size


def clone_runtime(runtime_dir: Path, force: bool):
    inference_path = runtime_dir / "inference.py"
    if inference_path.exists() and not force:
        print(f"Wav2Lip runtime already exists: {runtime_dir}")
        return

    if force and runtime_dir.exists():
        shutil.rmtree(runtime_dir)

    runtime_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--depth", "1", WAV2LIP_REPO, str(runtime_dir)])


def download_url(url: str, output_path: Path, min_size: int):
    if is_ready_file(output_path, min_size):
        print(f"File already exists: {output_path}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".download")
    if tmp_path.exists():
        tmp_path.unlink()
    print(f"Downloading {url} -> {output_path}")
    urllib.request.urlretrieve(url, tmp_path)
    if not is_ready_file(tmp_path, min_size):
        raise RuntimeError(f"Downloaded file is too small or empty: {tmp_path}")
    tmp_path.replace(output_path)


def download_gdrive_file(file_id: str, output_path: Path, min_size: int):
    if is_ready_file(output_path, min_size):
        print(f"File already exists: {output_path}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".download")
    if tmp_path.exists():
        tmp_path.unlink()
    run([sys.executable, "-m", "gdown", "--id", file_id, "-O", str(tmp_path)])
    if not is_ready_file(tmp_path, min_size):
        raise RuntimeError(f"Downloaded checkpoint is too small or empty: {tmp_path}")
    tmp_path.replace(output_path)


def replace_once(path: Path, old: str, new: str, label: str):
    text = path.read_text()
    if new in text:
        print(f"Patch already applied: {label}")
        return
    if old not in text:
        raise RuntimeError(f"Could not find expected source block for patch: {label} in {path}")
    path.write_text(text.replace(old, new, 1))
    print(f"Applied patch: {label}")


def patch_runtime(runtime_dir: Path):
    audio_path = runtime_dir / "audio.py"
    inference_path = runtime_dir / "inference.py"
    if not audio_path.exists() or not inference_path.exists():
        raise RuntimeError(f"Wav2Lip runtime is incomplete: {runtime_dir}")

    replace_once(
        audio_path,
        "return librosa.filters.mel(hp.sample_rate, hp.n_fft, n_mels=hp.num_mels,",
        "return librosa.filters.mel(sr=hp.sample_rate, n_fft=hp.n_fft, n_mels=hp.num_mels,",
        "librosa 0.10 keyword-only mel args",
    )
    replace_once(
        inference_path,
        "map_location=lambda storage, loc: storage)",
        "map_location='cpu')",
        "CPU torch.load map_location",
    )
    replace_once(
        inference_path,
        """def load_model(path):
\tmodel = Wav2Lip()
\tprint("Load checkpoint from: {}".format(path))
\tcheckpoint = _load(path)
\ts = checkpoint["state_dict"]
""",
        """def load_model(path):
\tprint("Load checkpoint from: {}".format(path))
\tcheckpoint = _load(path)
\tif not isinstance(checkpoint, dict) and hasattr(checkpoint, 'forward'):
\t\tmodel = checkpoint.to(device)
\t\treturn model.eval()

\tmodel = Wav2Lip()
\ts = checkpoint["state_dict"]
""",
        "TorchScript checkpoint support",
    )
    replace_once(
        inference_path,
        """\tbatch_size = args.face_det_batch_size
\t
\twhile 1:
\t\tpredictions = []
\t\ttry:
\t\t\tfor i in tqdm(range(0, len(images), batch_size)):
\t\t\t\tpredictions.extend(detector.get_detections_for_batch(np.array(images[i:i + batch_size])))
""",
        """\tbatch_size = args.face_det_batch_size
\tstride = max(1, int(os.environ.get('WAV2LIP_FACE_DET_STRIDE', '1')))
\tif stride > 1:
\t\tsample_indices = list(range(0, len(images), stride))
\t\tif sample_indices[-1] != len(images) - 1:
\t\t\tsample_indices.append(len(images) - 1)
\t\tdetect_images = [images[i] for i in sample_indices]
\t\tprint('Face detection stride: {} ({} sampled / {} frames)'.format(stride, len(detect_images), len(images)))
\telse:
\t\tsample_indices = None
\t\tdetect_images = images
\t
\twhile 1:
\t\tpredictions = []
\t\ttry:
\t\t\tfor i in tqdm(range(0, len(detect_images), batch_size)):
\t\t\t\tpredictions.extend(detector.get_detections_for_batch(np.array(detect_images[i:i + batch_size])))
""",
        "sampled face detection",
    )
    replace_once(
        inference_path,
        """\t\tbreak

\tresults = []
\tpady1, pady2, padx1, padx2 = args.pads
\tfor rect, image in zip(predictions, images):
\t\tif rect is None:
\t\t\tcv2.imwrite('temp/faulty_frame.jpg', image) # check this frame where the face was not detected.
\t\t\traise ValueError('Face not detected! Ensure the video contains a face in all the frames.')

\t\ty1 = max(0, rect[1] - pady1)
\t\ty2 = min(image.shape[0], rect[3] + pady2)
\t\tx1 = max(0, rect[0] - padx1)
\t\tx2 = min(image.shape[1], rect[2] + padx2)
\t\t
\t\tresults.append([x1, y1, x2, y2])

\tboxes = np.array(results)
\tif not args.nosmooth: boxes = get_smoothened_boxes(boxes, T=5)
\tresults = [[image[y1: y2, x1:x2], (y1, y2, x1, x2)] for image, (x1, y1, x2, y2) in zip(images, boxes)]
""",
        """\t\tbreak

\tif sample_indices is not None:
\t\tsampled_predictions = predictions
\t\tpredictions = []
\t\tfor frame_idx in range(len(images)):
\t\t\tnearest_idx = min(int(round(frame_idx / float(stride))), len(sample_indices) - 1)
\t\t\tpredictions.append(sampled_predictions[nearest_idx])

\tboxes = []
\tmissing_count = 0
\tpady1, pady2, padx1, padx2 = args.pads
\tfor rect, image in zip(predictions, images):
\t\tif rect is None:
\t\t\tcv2.imwrite('temp/faulty_frame.jpg', image) # check this frame where the face was not detected.
\t\t\tboxes.append(None)
\t\t\tmissing_count += 1
\t\t\tcontinue

\t\ty1 = max(0, rect[1] - pady1)
\t\ty2 = min(image.shape[0], rect[3] + pady2)
\t\tx1 = max(0, rect[0] - padx1)
\t\tx2 = min(image.shape[1], rect[2] + padx2)
\t\t
\t\tboxes.append([x1, y1, x2, y2])

\tif missing_count:
\t\tprint('Face not detected in {} frame(s); preserving those original frames.'.format(missing_count))
\telif not args.nosmooth:
\t\tboxes = get_smoothened_boxes(np.array(boxes), T=5)

\tresults = []
\tfor image, box in zip(images, boxes):
\t\tif box is None:
\t\t\tresults.append(None)
\t\t\tcontinue
\t\tx1, y1, x2, y2 = [int(v) for v in box]
\t\tresults.append([image[y1: y2, x1:x2], (y1, y2, x1, x2)])
""",
        "preserve frames without detected faces",
    )
    replace_once(
        inference_path,
        """\t\tface, coords = face_det_results[idx].copy()

\t\tface = cv2.resize(face, (args.img_size, args.img_size))
""",
        """\t\tface_result = face_det_results[idx]
\t\tif face_result is None:
\t\t\tface = np.zeros((args.img_size, args.img_size, 3), dtype=np.uint8)
\t\t\tcoords = None
\t\telse:
\t\t\tface, coords = face_result.copy()

\t\tface = cv2.resize(face, (args.img_size, args.img_size))
""",
        "skip model paste for missing-face frames",
    )
    replace_once(
        inference_path,
        """\t\tfor p, f, c in zip(pred, frames, coords):
\t\t\ty1, y2, x1, x2 = c
""",
        """\t\tfor p, f, c in zip(pred, frames, coords):
\t\t\tif c is None:
\t\t\t\tout.write(f)
\t\t\t\tcontinue
\t\t\ty1, y2, x1, x2 = c
""",
        "write original frame when no face is available",
    )


def print_next_steps(runtime_dir: Path, checkpoint_path: Path):
    print("\nWav2Lip runtime is ready.")
    print(f"Runtime:    {runtime_dir}")
    print(f"Checkpoint: {checkpoint_path}")
    print("\nStrict preflight:")
    print(
        "installer_files/env/bin/python run-youtube-pipeline.py "
        '"https://youtu.be/VIDEO_ID" --preflight --enable-lip-sync '
        "--lip-sync-engine Wav2Lip --no-audio-only-fallback"
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Install the local Wav2Lip runtime used by the Voice-Pro lip-sync pipeline.")
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--checkpoint-path", type=Path, default=DEFAULT_CHECKPOINT_PATH)
    parser.add_argument("--checkpoint-drive-id", default=WAV2LIP_CHECKPOINT_DRIVE_ID)
    parser.add_argument("--force-clone", action="store_true", help="Delete and re-clone the Wav2Lip runtime directory.")
    parser.add_argument("--skip-downloads", action="store_true", help="Only clone/patch the runtime; do not download model files.")
    return parser.parse_args()


def main():
    args = parse_args()
    runtime_dir = args.runtime_dir.resolve()
    checkpoint_path = args.checkpoint_path.resolve()

    clone_runtime(runtime_dir, args.force_clone)
    patch_runtime(runtime_dir)

    if not args.skip_downloads:
        download_url(
            S3FD_URL,
            runtime_dir / "face_detection" / "detection" / "sfd" / "s3fd.pth",
            min_size=1_000_000,
        )
        download_gdrive_file(args.checkpoint_drive_id, checkpoint_path, min_size=50_000_000)

    print_next_steps(runtime_dir, checkpoint_path)


if __name__ == "__main__":
    os.chdir(PROJECT_ROOT)
    main()
