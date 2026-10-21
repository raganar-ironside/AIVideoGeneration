"""Optional Streamlit reviewer: launch with streamlit run .../storyboard_app.py -- JOB_DIR"""
import sys
from pathlib import Path
import streamlit as st
from historyforgeai.application.services.storyboard import load, save, apply_approved, approve_available_images
from historyforgeai.application.services.scene_alignment import duplicate_image_groups, scene_mapping_issues, swap_scene_images
from historyforgeai.application.services.script_review import save_script_edits, approve_script, script_approved
from historyforgeai.domain.models import ShortPlan
from historyforgeai.infrastructure.assets.commons_candidates import search_commons

st.set_page_config(page_title='HistoryForgeAI Storyboard',layout='wide')
st.title('HistoryForgeAI · Storyboard review')
job_dir = Path(sys.argv[-1]).expanduser().resolve() if len(sys.argv)>1 and sys.argv[-1] != '--' else None
if not job_dir or not (job_dir/'storyboard.json').exists():
    st.info('Launch: streamlit run src/historyforgeai/interfaces/storyboard_app.py -- workspace/jobs/JOB_ID')
    st.stop()
plan_path = job_dir / 'scene_plan.json'
if not plan_path.is_file():
    st.error('Missing scene_plan.json')
    st.stop()
plan = ShortPlan.model_validate_json(plan_path.read_text(encoding='utf-8'))
st.subheader('Step 1 · Review the script')
st.caption('Edit individual scenes. Save first, then approve. Changed scenes return to pending image review.')
with st.form('script_editor'):
    edits = {}
    for scene in plan.scenes:
        with st.expander(f'Script scene {scene.index}', expanded=True):
            narration = st.text_area('Narration', scene.narration, key=f'narration_{scene.index}', height=110)
            visual = st.text_area('Visual description', scene.visual_description, key=f'visual_{scene.index}')
            query = st.text_input('Image search query', scene.asset_query, key=f'query_{scene.index}')
            edits[scene.index] = {'narration': narration, 'visual_description': visual, 'asset_query': query}
    save_script = st.form_submit_button('Save script changes')
if save_script:
    try:
        changed = save_script_edits(job_dir, edits)
        st.success(f"Saved changes to scenes {changed}. Original AI draft preserved." if changed else 'No changes to save.')
        st.rerun()
    except Exception as exc:
        st.error(str(exc))
if script_approved(job_dir):
    st.success('Script approved · no changes since approval')
else:
    st.warning('Script needs approval before narration or rendering')
    if st.button('Approve current script', type='primary'):
        try:
            approve_script(job_dir)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
st.divider()
st.subheader('Step 2 · Review scene images')
board_path=job_dir/'storyboard.json'
board=load(board_path)
st.caption(f'{board.topic} · {len(board.shots)} scenes')

st.markdown('**Scene-to-narration alignment check**')
st.caption('Each numbered image must illustrate the narration directly beneath it. '
           'Scene-audio timing cannot fix an image attached to the wrong scene.')
issues = scene_mapping_issues(plan, board)
for issue in issues:
    st.warning(issue)
duplicate_groups = duplicate_image_groups(board)
for group in duplicate_groups:
    st.warning('Same image content used in scenes ' + ', '.join(map(str, group)) +
               '. Reuse may be intentional, but verify it matches each narration.')
gallery = st.columns(min(4, max(1, len(board.shots))))
for i, shot in enumerate(board.shots):
    with gallery[i % len(gallery)]:
        st.markdown(f'**Scene {shot.scene_index}**')
        if shot.candidate_image and Path(shot.candidate_image).expanduser().is_file():
            st.image(str(Path(shot.candidate_image).expanduser()), width=180)
        else:
            st.caption('No image assigned')
        st.caption('Spoken: ' + shot.narration)
        st.caption('Expected visual: ' + shot.visual_description)

scene_indexes = [shot.scene_index for shot in board.shots]
if len(scene_indexes) >= 2:
    left, right = st.columns(2)
    with left:
        swap_from = st.selectbox('Image in scene', scene_indexes, key='image_swap_from')
    with right:
        swap_to = st.selectbox('Swap with image in scene', scene_indexes,
                               index=1, key='image_swap_to')
    if st.button('Swap scene images', help='Save review edits first. Both swapped images must be approved again.'):
        try:
            swap_scene_images(board, swap_from, swap_to)
            save(board_path, board)
            for idx in (swap_from, swap_to):
                for prefix in ('path', 'url', 'lic', 'attr', 'status'):
                    st.session_state.pop(f'{prefix}{idx}', None)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
st.caption('After swapping, review the two images and approve them again before rendering.')


# This callback runs before Streamlit redraws widgets, so status selectors
# reflect bulk approval immediately without requiring a second click.
def bulk_approve():
    latest = load(board_path)
    for shot in latest.shots:
        idx = shot.scene_index
        for field, prefix in (
            ('candidate_image', 'path'),
            ('source_url', 'url'),
            ('license', 'lic'),
            ('attribution', 'attr'),
        ):
            key = f'{prefix}{idx}'
            if key in st.session_state:
                setattr(shot, field, st.session_state[key] or None)
        shot.status = st.session_state.get(f'status{idx}', shot.status)
    approved, skipped = approve_available_images(latest)
    save(board_path, latest)
    for idx in approved:
        st.session_state[f'status{idx}'] = 'approved'
    st.session_state['bulk_approval_feedback'] = (approved, skipped)

st.button(
    'Approve All Images',
    on_click=bulk_approve,
    help='Approves all readable local images and skips missing or invalid files.',
)
feedback = st.session_state.pop('bulk_approval_feedback', None)
if feedback is not None:
    approved, skipped = feedback
    st.success(f'Approved {len(approved)} image(s).')
    if skipped:
        st.warning('Skipped scenes with missing or unreadable images: ' + ', '.join(map(str, skipped)))

for shot in board.shots:
    with st.expander(f'Scene {shot.scene_index}: {shot.narration[:90]}',expanded=True):
        st.write(shot.narration)
        st.caption(shot.visual_description)
        scene_audio_path = job_dir / f'narration_scene_{shot.scene_index:02d}.wav'
        if scene_audio_path.is_file():
            st.caption('Last generated narration for this scene — listen and compare with the image')
            st.audio(str(scene_audio_path))

        st.write('Characters: '+(', '.join(shot.character_ids) or 'none'))
        if shot.candidate_image and Path(shot.candidate_image).is_file():
            st.image(shot.candidate_image,width=280)
        new_path=st.text_input('Approved local image path',value=shot.candidate_image or '',key=f'path{shot.scene_index}')
        shot.candidate_image=new_path or None
        shot.source_url=st.text_input('Source URL',value=shot.source_url or '',key=f'url{shot.scene_index}') or None
        shot.license=st.text_input('License / usage rights',value=shot.license or '',key=f'lic{shot.scene_index}') or None
        shot.attribution=st.text_input('Attribution',value=shot.attribution or '',key=f'attr{shot.scene_index}') or None
        shot.status=st.selectbox('Review status',['pending_review','approved','rejected'],
            index=['pending_review','approved','rejected'].index(shot.status),key=f'status{shot.scene_index}')
        if st.button('Search Wikimedia Commons',key=f'search{shot.scene_index}'):
            try:
                for candidate in search_commons(shot.search_query):
                    st.markdown(f"[{candidate['title']}]({candidate['source_url']}) · {candidate['license']} · {candidate['attribution']}")
                    if candidate['preview_url']: st.image(candidate['preview_url'],width=180)
                st.info('Download a chosen image manually, review its license, and enter its local path above.')
            except Exception as exc: st.error(str(exc))
if st.button('Save review',type='primary'):
    save(board_path,board)
    st.success('Storyboard saved')
if st.button('Apply approved images to scene plan'):
    save(board_path,board)
    try:
        count=apply_approved(job_dir/'scene_plan.json',board_path)
        st.success(f'Applied {count} approved images')
    except Exception as exc: st.error(str(exc))

st.divider()
st.subheader('Step 3 · Narration Studio')
st.caption('Preview audio before spending requests on a full render. Settings apply to this action only.')
import os
import subprocess
from historyforgeai.infrastructure.speech.factory import build_speech

provider = st.selectbox('Narration engine', ['edge', 'gemini', 'kokoro'], index=0)
voice_defaults = {'edge': 'hi-IN-MadhurNeural', 'gemini': 'Charon', 'kokoro': ''}
if provider == 'edge':
    edge_voice_options = {
        'Madhur — Hindi male': 'hi-IN-MadhurNeural',
        'Swara — Hindi female': 'hi-IN-SwaraNeural',
        'Custom voice name': 'custom',
    }
    voice_choice = st.selectbox('Edge voice', list(edge_voice_options))
    voice = (st.text_input('Custom Edge voice', value='hi-IN-MadhurNeural')
             if edge_voice_options[voice_choice] == 'custom'
             else edge_voice_options[voice_choice])
else:
    voice = st.text_input('Voice name', value=voice_defaults[provider], key=f'voice_{provider}')
if provider == 'edge':
    st.caption('Edge native speech settings')
    if 'edge_pitch' not in st.session_state:
        st.session_state.edge_pitch = -10
    if 'edge_volume' not in st.session_state:
        st.session_state.edge_volume = 0
    if 'edge_bass' not in st.session_state:
        st.session_state.edge_bass = 2
    if st.button('Reset Edge voice controls'):
        st.session_state.edge_pitch = 0
        st.session_state.edge_volume = 0
        st.session_state.edge_bass = 0
        st.rerun()
    edge_pitch = st.slider('Edge pitch (Hz)', min_value=-50, max_value=50, step=5, key='edge_pitch')
    edge_volume = st.slider('Edge volume (%)', min_value=-50, max_value=50, step=5, key='edge_volume')
    edge_bass = st.slider('Bass enhancement (dB)', min_value=0, max_value=8, step=1, key='edge_bass')

speed = st.slider('Speaking speed', min_value=0.85, max_value=1.50, value=1.20, step=0.05)
preset = st.selectbox('Voice style', ['normal', 'documentary', 'epic'], index=0)
preview_text = st.text_area(
    'Preview text',
    value='दक्षिण भारत के तंजावुर में स्थित बृहदीश्वर मंदिर, चोल साम्राज्य की प्रसिद्ध स्थापत्य कला का अद्भुत उदाहरण है।',
    height=100,
)
st.caption('Gemini preview consumes one API request. Rendering with scene audio may consume one request per scene.')
def narration_env():
    env = os.environ.copy()
    env['SPEECH_PROVIDER'] = provider
    env['VOICE_PRESET'] = preset
    env['VOICE_SPEED'] = str(speed)
    if provider == 'edge':
        env['EDGE_TTS_VOICE'] = voice
        env['EDGE_TTS_PITCH'] = f'{edge_pitch:+d}Hz'
        env['EDGE_TTS_VOLUME'] = f'{edge_volume:+d}%'
        env['VOICE_BASS_DB'] = str(edge_bass)
        env['VOICE_PITCH_SEMITONES'] = '0'
    elif provider == 'gemini':
        env['GEMINI_TTS_VOICE'] = voice
    return env

if st.button('Generate narration preview'):
    if not preview_text.strip():
        st.warning('Enter preview text first.')
    else:
        try:
            # build_speech reads process environment; restore it after synthesis.
            keys = ['SPEECH_PROVIDER', 'VOICE_PRESET', 'VOICE_SPEED', 'EDGE_TTS_VOICE', 'GEMINI_TTS_VOICE', 'EDGE_TTS_PITCH', 'EDGE_TTS_VOLUME', 'VOICE_BASS_DB', 'VOICE_PITCH_SEMITONES']
            previous = {key: os.environ.get(key) for key in keys}
            try:
                os.environ.update({key: value for key, value in narration_env().items() if key in keys})
                preview_path = job_dir / 'narration_preview.wav'
                build_speech().synthesize(preview_text.strip(), str(preview_path))
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            st.audio(str(preview_path))
            st.success('Preview generated. Listen before rendering.')
        except Exception as exc:
            st.error(f'Preview failed: {exc}')
preview_path = job_dir / 'narration_preview.wav'
if preview_path.is_file():
    st.audio(str(preview_path))

st.caption('Full render overwrites short.mp4 and narration.wav. Back up existing files first.')
confirm_render = st.checkbox('I verified that every numbered image matches its spoken narration and want to render')
if st.button('Render with selected narration', disabled=not confirm_render):
    try:
        cmd = [
            sys.executable, '-m', 'historyforgeai.cli', 'render',
            '--job', job_dir.name, '--generate-audio', '--scene-audio',
            '--motion', 'zoom_in',
        ]
        result = subprocess.run(cmd, env=narration_env(), capture_output=True, text=True, timeout=1200)
        if result.returncode:
            st.error(result.stderr[-3000:] or result.stdout[-3000:])
        else:
            st.success('Video rendered')
            video = job_dir / 'short.mp4'
            if video.is_file():
                st.video(str(video))
    except Exception as exc:
        st.error(f'Render failed: {exc}')
