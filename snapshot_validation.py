"""Archive validation labels and content hashes before training; never modify source data."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def snapshot(output, root=Path('.')):
    images = sorted(p for p in (root/'data/validation/images').rglob('*')
                    if p.suffix.lower() in {'.jpg', '.jpeg', '.png'})
    if not images:
        raise ValueError('Validation contains no images')
    output.mkdir(parents=True, exist_ok=False)
    records = []
    for image in images:
        rel = image.relative_to(root/'data/validation/images')
        label = root/'data/validation/labels'/rel.with_suffix('.txt')
        record = dict(image=rel.as_posix(), image_sha256=digest(image), label_sha256=None)
        if label.exists():
            target = output/'labels'/rel.with_suffix('.txt')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(label, target)
            record['label_sha256'] = digest(target)
        records.append(record)
    config = {}
    for name in ('data.yaml', 'custom_data/classes.txt', 'val_split.txt'):
        src = root/name
        shutil.copy2(src, output/src.name)
        config[name] = digest(output/src.name)
    identity = dict(images=records, classes_sha256=config['custom_data/classes.txt'])
    version = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    manifest = dict(version=version, images=records, config_sha256=config,
                    note='Labels are archived. Images are identified by SHA256, not copied; retain original images for replay.')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Validation version: {version}; snapshot: {output}')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    snapshot(Path(args.output))
