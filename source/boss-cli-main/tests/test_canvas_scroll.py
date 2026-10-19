import base64
import io

from PIL import Image, ImageDraw

from scripts.probe_recommend_canvas import _continuous, _stitch_scrolled, capture_scrolled_canvas


def test_scrolled_canvas_only_stitches_matching_transparent_overlaps(tmp_path):
    long = Image.new('RGBA', (400, 1000), (0, 0, 0, 0))
    draw = ImageDraw.Draw(long)
    for y in range(20, 1000, 25):
        draw.text((20, y), f'candidate resume line {y}', fill=(20, 20, 20, 255))
    first = {'file': 'canvas-000.png', 'top': 0, 'canvas': {'width': 400, 'height': 600, 'css_height': 600}}
    second = {'file': 'canvas-001.png', 'top': 300, 'canvas': {'width': 400, 'height': 600, 'css_height': 600}}
    long.crop((0, 0, 400, 600)).save(tmp_path / first['file'])
    long.crop((0, 300, 400, 900)).save(tmp_path / second['file'])
    assert _continuous(first, second, tmp_path)
    _stitch_scrolled(tmp_path, [first, second], 900)
    with Image.open(tmp_path / 'resume-long.png') as combined:
        assert combined.size == (400, 900)
        assert combined.getpixel((0, 0)) == (255, 255, 255)
    wrong = Image.new('RGBA', (400, 600), (30, 30, 30, 255))
    wrong.save(tmp_path / second['file'])
    assert not _continuous(first, second, tmp_path)


def test_scrolled_probe_reaches_bottom_and_saves_reviewable_long_image(tmp_path):
    long = Image.new('RGBA', (400, 900), (0, 0, 0, 0))
    draw = ImageDraw.Draw(long)
    for y in range(20, 900, 25):
        draw.text((20, y), f'resume line {y}', fill=(20, 20, 20, 255))

    class Session:
        def call(self, operation, args):
            assert operation == 'resume_canvas'
            assert args['action'] == 'segment'
            top = args['top']
            assert top in (0, 300)
            buffer = io.BytesIO()
            long.crop((0, top, 400, top + 600)).save(buffer, format='PNG')
            return {'top': top, 'height': 600, 'total': 900,
                    'canvas': {'width': 400, 'height': 600, 'css_height': 600},
                    'png': base64.b64encode(buffer.getvalue()).decode()}

    manifest = {'pages': [], 'status': 'partial'}
    capture_scrolled_canvas(Session(), 'candidate', 'capture',
                            {'top': 0, 'height': 600, 'total': 900, 'frame_url': 'test'},
                            {'canvas_count': 1}, tmp_path, manifest, 3)
    assert manifest['status'] == 'canvas_segments_unverified'
    assert manifest['stitched'] == 'resume-long.png'
    assert len(manifest['pages']) == 2
