"""Optional Streamlit reviewer: launch with streamlit run .../storyboard_app.py -- JOB_DIR"""
import sys
from pathlib import Path
import streamlit as st
from historyforgeai.application.services.storyboard import load, save, apply_approved, approve_saved_images
from historyforgeai.application.services.scene_alignment import duplicate_image_groups, scene_mapping_issues, swap_scene_images
from historyforgeai.application.services.script_review import save_script_edits, approve_script, script_approved
from historyforgeai.domain.models import ShortPlan
from historyforgeai.infrastructure.assets.commons_candidates import search_commons
from historyforgeai.application.services.image_candidates import recover_missing_candidates

st.set_page_config(page_title='HistoryForgeAI Storyboard',layout='wide')
st.title('HistoryForgeAI · Storyboard review')
job_dir = Path(sys.argv[-1]).expanduser().resolve() if len(sys.argv)>1 and sys.argv[-1] != '--' else None
if not job_dir or not (job_dir/'storyboard.json').exists():
    st.info('Launch: streamlit run src/historyforgeai/interfaces/storyboard_app.py -- workspace/jobs/JOB_ID')
    st.stop()
# Streamlit retains widget state across page reruns and even job switches.
# Do not let paths from a different job overwrite this job's storyboard.
if st.session_state.get('_active_storyboard_job') != str(job_dir):
    for key in list(st.session_state):
        if key.startswith(('path', 'url', 'lic', 'attr', 'status', 'upload',
                           'narration_', 'visual_', 'query_')):
            st.session_state.pop(key, None)
    st.session_state.pop('image_swap_from', None)
    st.session_state.pop('image_swap_to', None)
    st.session_state['_active_storyboard_job'] = str(job_dir)
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
upload_feedback = st.session_state.pop('upload_feedback', None)
if upload_feedback:
    st.success(f'Scene {upload_feedback[0]} image imported. Review it, then approve.')

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
    # Use the saved storyboard as the source of truth. Session-state fields
    # may be stale or empty after uploads and must not overwrite image paths.
    approved, skipped = approve_saved_images(board_path)
    latest = load(board_path)
    for shot in latest.shots:
        idx = shot.scene_index
        # Refresh every widget from the persisted result before rerun.
        for field, prefix in (
            ('candidate_image', 'path'),
            ('source_url', 'url'),
            ('license', 'lic'),
            ('attribution', 'attr'),
        ):
            st.session_state[f'{prefix}{idx}'] = getattr(shot, field) or ''
        st.session_state[f'status{idx}'] = shot.status
    st.session_state['bulk_approval_feedback'] = (approved, skipped)

st.caption('Save any manual path or metadata edits with **Save review** before bulk approval.')
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

if st.button('Recover missing images from job assets',
             help='Reattach candidate_scene_XX.jpg files when an earlier review cleared their assignments.'):
    try:
        restored = recover_missing_candidates(job_dir)
        for idx in restored:
            for prefix in ('path', 'url', 'lic', 'attr', 'status'):
                st.session_state.pop(f'{prefix}{idx}', None)
        st.session_state['recovery_feedback'] = restored
        st.rerun()
    except (ValueError, OSError) as exc:
        st.error(f'Recovery failed: {exc}')
recovered = st.session_state.pop('recovery_feedback', None)
if recovered is not None:
    if recovered:
        st.success('Recovered scene images: ' + ', '.join(map(str, recovered)) +
                   '. Review and approve them again.')
    else:
        st.info('No missing scene images could be recovered from job assets.')

for shot in board.shots:
    # Set defaults in session state only when the scene widget is first
    # created. After uploads or bulk approval, callbacks can safely update
    # these keys without conflicting with value=/index= widget defaults.
    idx = shot.scene_index
    for prefix, value in (
        ('path', shot.candidate_image),
        ('url', shot.source_url),
        ('lic', shot.license),
        ('attr', shot.attribution),
    ):
        st.session_state.setdefault(f'{prefix}{idx}', value or '')
    st.session_state.setdefault(f'status{idx}', shot.status)
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
        uploaded = st.file_uploader(
            'Browse / Upload Image (opens your computer file picker)',
            type=['png', 'jpg', 'jpeg', 'webp'],
            key=f'upload{shot.scene_index}',
            help='Select a picture from Windows File Explorer or your browser device. '
                 'The image is copied into this job and awaits review.',
        )
        if st.button('Use uploaded image for this scene',
                     key=f'use_upload{shot.scene_index}',
                     disabled=uploaded is None):
            try:
                # Import against the latest saved storyboard, not the in-memory
                # board. Earlier widgets in this rerun may have stale paths;
                # saving them here could erase other scenes' imported images.
                from historyforgeai.application.services.image_candidates import create_uploaded_candidate
                destination = create_uploaded_candidate(
                    job_dir, shot.scene_index, uploaded.getvalue()
                )
                for prefix in ('path', 'url', 'lic', 'attr', 'status'):
                    st.session_state.pop(f'{prefix}{shot.scene_index}', None)
                st.session_state['upload_feedback'] = (
                    shot.scene_index, str(destination)
                )
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(f'Upload failed: {exc}')
        new_path=st.text_input('Approved local image path',key=f'path{shot.scene_index}')
        shot.candidate_image=new_path or None
        shot.source_url=st.text_input('Source URL',key=f'url{shot.scene_index}') or None
        shot.license=st.text_input('License / usage rights',key=f'lic{shot.scene_index}') or None
        shot.attribution=st.text_input('Attribution',key=f'attr{shot.scene_index}') or None
        shot.status=st.selectbox('Review status',['pending_review','approved','rejected'],
            key=f'status{shot.scene_index}')
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
    # Apply only the saved, approved storyboard; never persist potentially
    # stale values assembled during this Streamlit rerun.
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


st.divider()
st.subheader('Step 4 · Cinematic Finishing')
st.caption('Add licensed background music and smooth scene transitions to your existing '
           'synchronized video. This does not regenerate narration, change approvals, '
           'or overwrite short.mp4.')
from historyforgeai.application.services.cinematic_finishing import (
    find_background_music, import_background_music, finish_video,
)

rendered_short = job_dir / 'short.mp4'
if not rendered_short.is_file():
    st.info('Render the synchronized Short in Step 3 first.')
else:
    st.markdown('**Background music**')
    st.caption('Download an MP3/WAV/M4A from YouTube Audio Library, Pixabay or another '
               'source whose license permits your intended use. Keep any required attribution.')
    music_upload = st.file_uploader(
        'Choose a background music file from your computer',
        type=['mp3', 'wav', 'm4a'],
        key='cinematic_music_upload',
        help='The music is copied into this job; maximum 40 MB.',
    )
    if st.button('Save music to this job', disabled=music_upload is None):
        try:
            imported = import_background_music(
                job_dir, music_upload.name, music_upload.getvalue()
            )
            st.success(f'Saved background music: {imported.name}')
            st.rerun()
        except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            st.error(f'Music import failed: {exc}')
    saved_music = find_background_music(job_dir)
    if saved_music:
        st.caption(f'Saved track: {saved_music.name}')
        st.audio(str(saved_music))
    use_music = st.checkbox(
        'Include saved background music',
        value=bool(saved_music),
        disabled=saved_music is None,
        key='cinematic_use_music',
    )
    volume = st.slider(
        'Background music volume (%)', min_value=0, max_value=40, value=15,
        step=1, disabled=not use_music, key='cinematic_volume',
    )
    duck = st.checkbox(
        'Automatically lower music while narration plays',
        value=True, disabled=not use_music, key='cinematic_duck',
    )
    st.markdown('**Scene transitions**')
    transition_label = st.selectbox(
        'Transition style', ['Cinematic crossfade', 'Hard cut (original timing)'],
        key='cinematic_transition',
    )
    crossfade = transition_label == 'Cinematic crossfade'
    fade_seconds = st.slider(
        'Crossfade duration (seconds)', min_value=0.2, max_value=1.0,
        value=0.4, step=0.1, disabled=not crossfade,
        key='cinematic_fade_seconds',
    )
    st.caption('Crossfades begin at existing narration boundaries, briefly blending '
               'the outgoing frame into the next scene without moving audio timing. '
               'No changes are made to the original video.')
    if st.button(
        'Create cinematic video',
        type='primary',
        disabled=not crossfade and not (use_music and saved_music),
    ):
        try:
            finished = finish_video(
                job_dir,
                music_path=saved_music if use_music else None,
                music_volume=volume / 100,
                duck_music=duck,
                transition='crossfade' if crossfade else 'cut',
                transition_seconds=fade_seconds,
            )
            st.success(f'Cinematic version ready: {finished.name}')
        except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            st.error(f'Cinematic finishing failed: {exc}')
    cinematic_output = job_dir / 'short_cinematic.mp4'
    if cinematic_output.is_file():
        st.markdown('**Cinematic video preview**')
        st.video(str(cinematic_output))
        st.caption(f'Saved to {cinematic_output}')
