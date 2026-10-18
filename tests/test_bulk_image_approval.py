from PIL import Image

from historyforgeai.application.services.storyboard import (
    Shot, Storyboard, approve_available_images, load, save,
)


def shot(index, path=None, status='pending_review'):
    return Shot(scene_index=index, narration='Narration',
                visual_description='Temple', search_query='temple',
                candidate_image=str(path) if path else None, status=status)


def test_bulk_approve_valid_and_skip_missing_or_corrupt(tmp_path):
    good = tmp_path / 'good.png'
    Image.new('RGB', (24, 24)).save(good)
    bad = tmp_path / 'bad.png'
    bad.write_bytes(b'not an image')
    board = Storyboard(topic='Temple', shots=[
        shot(1, good),
        shot(2, tmp_path / 'missing.png'),
        shot(3, bad, 'rejected'),
        shot(4),
    ])
    assert approve_available_images(board) == ([1], [2, 3, 4])
    assert [s.status for s in board.shots] == [
        'approved', 'pending_review', 'rejected', 'pending_review'
    ]


def test_bulk_approve_persists_when_saved(tmp_path):
    good = tmp_path / 'good.png'
    Image.new('RGB', (24, 24)).save(good)
    board = Storyboard(topic='Temple', shots=[shot(1, good), shot(2, good, 'rejected')])
    assert approve_available_images(board) == ([1, 2], [])
    path = tmp_path / 'storyboard.json'
    save(path, board)
    assert [s.status for s in load(path).shots] == ['approved', 'approved']
