"""Optional Streamlit reviewer: launch with streamlit run .../storyboard_app.py -- JOB_DIR"""
import sys
from pathlib import Path
import streamlit as st
from historyforgeai.application.services.storyboard import load, save, apply_approved, approve_saved_images
from historyforgeai.application.services.scene_alignment import duplicate_image_groups, scene_mapping_issues, swap_scene_images
from historyforgeai.application.services.script_review import save_script_edits, approve_script, script_approved
from historyforgeai.domain.models import ShortPlan
from historyforgeai.config import ROOT
from dotenv import load_dotenv

# Streamlit does not pass through CLI settings(), so load local API credentials.
load_dotenv(ROOT / ".env")
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
                           'narration_', 'visual_', 'query_', 'cinematic_', 'cutout_')):
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
st.subheader('Step 2.5 · Illustrated character cutouts (Blender)')
st.caption('Generate a single character or import a 12-part puppet for the legacy v2 rig. '
           'For multiple characters and reusable motion clips, use the v3 builder below. '
           'Draft assets are never rendered before approval.')
from historyforgeai.application.services.illustrated_assets import (
    prepare_scene_assets, approve_scene_assets, reject_scene_assets, load_asset_draft,
    update_approved_scene_spec,
)
cutout_scene = st.selectbox(
    'Scene for cutout preparation', [shot.scene_index for shot in board.shots],
    key='cutout_scene',
)
cutout_shot = next(shot for shot in board.shots if shot.scene_index == cutout_scene)
cutout_provider = st.selectbox('Illustration source', ['gemini', 'openai', 'manual'], key='cutout_provider')
cutout_mode = st.selectbox(
    'Animation asset type', ['whole', 'body-arm', 'puppet'], key='cutout_mode',
    help='puppet imports 12 named PNG parts (manual); body-arm uses experimental AI edits.',
)
cutout_character_id = st.selectbox(
    'Approved character reference (optional)', [''] + cutout_shot.character_ids,
    key='cutout_character_id',
)
cutout_description = st.text_input(
    'Character appearance', value=', '.join(cutout_shot.character_ids),
    key=f'cutout_description_{cutout_scene}',
    help='Specify clothing, age, armour and illustration style to help consistency.',
)
cutout_upload = st.file_uploader(
    'Character reference or manual whole/body PNG', type=['png', 'jpg', 'jpeg', 'webp'],
    key=f'cutout_reference_{cutout_scene}',
) if cutout_mode != 'puppet' else None
cutout_puppet_uploads = (
    st.file_uploader(
        'Upload 12 transparent PNGs named torso.png, head.png, upper_arm_l.png, etc.',
        type=['png'], accept_multiple_files=True,
        key=f'cutout_puppet_parts_{cutout_scene}',
    ) if cutout_mode == 'puppet' and cutout_provider == 'manual' else []
)
if cutout_mode == 'puppet':
    from historyforgeai.application.services.puppet_templates import PUPPET_PARTS
    st.caption('Required: ' + ', '.join(name + '.png' for name in PUPPET_PARTS))
    if cutout_provider != 'manual':
        st.warning('Full 12-part puppet generation is not automated yet. Select Manual and upload separated PNGs.')
cutout_arm_upload = (
    st.file_uploader('Separate transparent arm PNG', type=['png', 'webp'],
                     key=f'cutout_arm_{cutout_scene}')
    if cutout_provider == 'manual' and cutout_mode == 'body-arm' else None
)
cutout_remove_bg = st.checkbox(
    'Remove opaque image background locally (requires rembg; may download model weights)',
    value=True, key='cutout_remove_bg',
)
cutout_generate_bg = st.checkbox(
    'Also generate an illustrated background as a NEW pending-review storyboard image',
    disabled=cutout_provider == 'manual', key='cutout_generate_bg',
)
cutout_paid = st.checkbox(
    'I authorize potentially billed Gemini/OpenAI image generation calls',
    disabled=cutout_provider == 'manual', key='cutout_paid',
)
from historyforgeai.application.services.image_api_budget import (
    usage_summary, job_budget_limit,
)
cutout_budget = st.number_input(
    'Estimated image API budget for this job (USD)',
    min_value=0.01, max_value=1000.0, value=job_budget_limit(), step=0.25,
    disabled=cutout_provider == 'manual', key='cutout_budget',
    help='An estimated request guard, NOT a provider billing limit. '
         'Actual charges depend on model and usage; check Google AI Studio billing.',
)
cutout_usage = usage_summary(job_dir)
st.caption(
    f"Image API attempts for this job: {cutout_usage['attempted_requests']} "
    f"· estimated spend: ${cutout_usage['estimated_spend_usd']:.2f}. "
    "Estimates are configurable and may differ from actual charges."
)
cutout_replace = st.checkbox('Replace an existing cutout draft', key='cutout_replace')
draft = load_asset_draft(job_dir, cutout_scene)
if st.button('Prepare cutout draft', disabled=cutout_provider != 'manual' and not cutout_paid):
    try:
        from io import BytesIO
        from PIL import Image
        uploads_dir = job_dir / 'animation' / 'uploads'
        uploads_dir.mkdir(parents=True, exist_ok=True)

        def save_cutout_upload(upload, name):
            if upload is None:
                return None
            raw = upload.getvalue()
            if not raw or len(raw) > 20 * 1024 * 1024:
                raise ValueError('Character upload must be under 20 MB')
            with Image.open(BytesIO(raw)) as image:
                image.load()
                path = uploads_dir / f'scene_{cutout_scene:02d}_{name}.png'
                image.save(path, format='PNG')
            return path

        source_path = save_cutout_upload(cutout_upload, 'reference')
        arm_path = save_cutout_upload(cutout_arm_upload, 'arm')
        if cutout_mode == 'puppet':
            if cutout_provider != 'manual':
                raise ValueError('Full puppet mode requires Manual source until parts-sheet generation is implemented')
            from historyforgeai.application.services.puppet_templates import PUPPET_PARTS
            names = [Path(upload.name).name for upload in cutout_puppet_uploads]
            required = {name + '.png' for name in PUPPET_PARTS}
            if len(names) != len(required) or set(names) != required:
                raise ValueError('Upload exactly the 12 required, uniquely named PNGs')
            puppet_dir = uploads_dir / f'scene_{cutout_scene:02d}_puppet'
            puppet_dir.mkdir(parents=True, exist_ok=True)
            for upload in cutout_puppet_uploads:
                raw = upload.getvalue()
                if not raw or len(raw) > 20 * 1024 * 1024:
                    raise ValueError('Each puppet PNG must be under 20 MB')
                with Image.open(BytesIO(raw)) as image:
                    image.load()
                    if 'A' not in image.getbands() and 'transparency' not in image.info:
                        raise ValueError(f'{upload.name} must have transparency')
                    image.save(puppet_dir / Path(upload.name).name, format='PNG')
            source_path = puppet_dir
        result = prepare_scene_assets(
            job_dir, cutout_scene, provider=cutout_provider, mode=cutout_mode,
            source=source_path, arm_source=arm_path,
            character_id=cutout_character_id or None,
            description=cutout_description, allow_paid=cutout_paid,
            image_budget_usd=cutout_budget if cutout_provider != 'manual' else None,
            remove_background=cutout_remove_bg,
            generate_background=cutout_generate_bg if cutout_provider != 'manual' else False,
            replace_draft=cutout_replace,
        )
        st.session_state['cutout_feedback'] = f'Draft created for scene {result.scene_index}; review before approval.'
        st.rerun()
    except Exception as exc:
        st.error(f'Cutout preparation failed: {exc}')
feedback = st.session_state.pop('cutout_feedback', None)
if feedback:
    st.success(feedback)
if draft:
    st.markdown(f'**Scene {cutout_scene} cutout draft — {draft.status}**')
    st.caption(draft.notes)
    draft_dir = job_dir / 'animation' / 'drafts' / f'scene_{cutout_scene:02d}'
    composite_preview = draft_dir / 'preview.png'
    if composite_preview.is_file():
        st.image(str(composite_preview), caption='Approximate first-frame composite (not a Blender render)', width=240)
    cols = st.columns(3 if len(draft.files) > 3 else max(1, len(draft.files)))
    for i, (name, filename) in enumerate(draft.files.items()):
        with cols[i % len(cols)]:
            asset_path = draft_dir / filename
            if asset_path.is_file():
                st.image(str(asset_path), caption=name, width=220)
    with st.expander('View generated prompts'):
        st.json(draft.prompts)
    if draft.background_candidate:
        st.info('Background candidate is pending separate image approval in Step 2.')
    if draft.status == 'pending_review':
        left, right = st.columns(2)
        with left:
            if st.button('Approve these cutouts', type='primary', key='cutout_approve'):
                try:
                    spec_path = approve_scene_assets(job_dir, cutout_scene)
                    st.session_state['cutout_feedback'] = f'Approved cutouts and created {spec_path.name}.'
                    st.rerun()
                except Exception as exc:
                    st.error(f'Approval failed: {exc}')
        with right:
            if st.button('Reject these cutouts', key='cutout_reject'):
                reject_scene_assets(job_dir, cutout_scene)
                st.rerun()
    if draft.status == 'approved':
        approved_spec = job_dir / 'animation' / f'scene_{cutout_scene:02d}.json'
        if approved_spec.is_file() and __import__('json').loads(approved_spec.read_text(encoding='utf-8')).get('version') == 2:
            with st.expander('Puppet rig builder — joints and pivots'):
                import json as _rig_json
                rig_data = _rig_json.loads(approved_spec.read_text(encoding='utf-8'))
                joint_rows = [
                    {
                        'id': part['id'], 'parent': part.get('parent') or '',
                        'x': part['x'], 'y': part['y'],
                        'pivot_x': part['pivot'][0], 'pivot_y': part['pivot'][1],
                        'width': part['width'], 'z': part['z'],
                    } for part in rig_data['parts']
                ]
                edited_joints = st.data_editor(
                    joint_rows, num_rows='fixed', hide_index=True,
                    disabled=['id'], use_container_width=True,
                    key=f'puppet_joint_editor_{cutout_scene}',
                )
                st.caption('Adjust bind positions and pivots to align your PNGs. '
                           'Parent IDs must match another part. Review a rendered scene '
                           'for actual parented motion.')
                if st.button('Save and reapprove joint rig', key=f'puppet_joint_save_{cutout_scene}'):
                    try:
                        rows = (edited_joints.to_dict('records')
                                if hasattr(edited_joints, 'to_dict') else edited_joints)
                        for part, row in zip(rig_data['parts'], rows):
                            part['parent'] = str(row['parent']).strip() or None
                            part['x'] = float(row['x'])
                            part['y'] = float(row['y'])
                            part['pivot'] = [float(row['pivot_x']), float(row['pivot_y'])]
                            part['width'] = float(row['width'])
                            part['z'] = int(row['z'])
                        update_approved_scene_spec(
                            job_dir, cutout_scene, _rig_json.dumps(rig_data),
                        )
                        st.success('Puppet rig joints reapproved.')
                        st.rerun()
                    except Exception as exc:
                        st.error(f'Joint update failed: {exc}')
            with st.expander('Adjust animation keyframes (advanced)'):
                edited_spec = st.text_area(
                    'Reviewed Blender animation JSON', value=approved_spec.read_text(encoding='utf-8'),
                    height=280, key=f'cutout_spec_editor_{cutout_scene}',
                )
                if st.button('Save and reapprove keyframes', key=f'cutout_update_{cutout_scene}'):
                    try:
                        update_approved_scene_spec(job_dir, cutout_scene, edited_spec)
                        st.success('Animation updated and reapproved; assets remain unchanged.')
                        st.rerun()
                    except Exception as exc:
                        st.error(f'Animation update failed: {exc}')
st.caption('Blender now uses parented puppet joints with easing. Full 12-part puppets '
           'require separately prepared PNGs and manual joint alignment; Gemini body-arm '
           'generation remains experimental. Automatic image separation is not implemented.')

with st.expander('Multi-character puppet scene builder · v3', expanded=False):
    from io import BytesIO as _BytesIO
    import re as _re
    from PIL import Image as _PILImage
    from historyforgeai.application.services.puppet_scene_builder import (
        stage_character, remove_character, add_motion_action, remove_motion_action,
        approve_multi_scene, load_multi_draft, preview_multi_scene, update_character_joints,
    )
    from historyforgeai.application.services.puppet_templates import PUPPET_PARTS
    from historyforgeai.application.services.motion_library import available_motions
    from historyforgeai.domain.models import ShortPlan as _ShortPlan
    multi_plan = _ShortPlan.model_validate_json(
        (job_dir / 'scene_plan.json').read_text(encoding='utf-8')
    )
    multi_scene_plan = next((sc for sc in multi_plan.scenes if sc.index == cutout_scene), None)
    multi_duration = multi_scene_plan.duration_seconds if multi_scene_plan else 6.0
    st.caption(f'Shared scene timeline: {multi_duration:.2f} seconds. '
               'Stage each character, add independent motions, preview the bind pose, '
               'then explicitly approve. Motions are keyframed 2D presets, not AI choreography.')
    multi_draft = load_multi_draft(job_dir, cutout_scene)
    multi_live = job_dir / 'animation' / f'scene_{cutout_scene:02d}.json'
    if multi_live.is_file() and __import__('json').loads(multi_live.read_text()).get('version') == 3:
        st.success('This scene has an approved v3 multi-character rig. '
                   'Adding or editing creates a separate draft.')
    st.markdown('**Add character**')
    multi_id = st.text_input('Character instance ID', value='shivaji',
                             key=f'multi_character_id_{cutout_scene}')
    cx, cy, cs, cz = st.columns(4)
    with cx:
        multi_x = st.number_input('Center X', value=.5, min_value=-1., max_value=2.,
                                  step=.05, key=f'multi_x_{cutout_scene}')
    with cy:
        multi_y = st.number_input('Center Y', value=.5, min_value=-1., max_value=2.,
                                  step=.05, key=f'multi_y_{cutout_scene}')
    with cs:
        multi_scale = st.number_input('Character scale', value=.7, min_value=.1, max_value=3.,
                                      step=.1, key=f'multi_scale_{cutout_scene}')
    with cz:
        multi_depth = st.number_input('Depth', value=0, min_value=-5, max_value=5,
                                      key=f'multi_depth_{cutout_scene}')
    multi_uploads = st.file_uploader(
        'Select 12 separate transparent PNGs for this character',
        type=['png'], accept_multiple_files=True,
        key=f'multi_uploads_{cutout_scene}_{multi_id}',
    )
    st.caption('Required: ' + ', '.join(p + '.png' for p in PUPPET_PARTS))
    if st.button('Stage character in scene', key=f'multi_stage_{cutout_scene}'):
        try:
            if not _re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,23}', multi_id):
                raise ValueError('Character ID must use letters, digits, hyphens or underscores')
            expected = {p + '.png' for p in PUPPET_PARTS}
            filenames = [file.name for file in multi_uploads]
            if len(filenames) != len(expected) or set(filenames) != expected:
                raise ValueError('Upload exactly the 12 required, uniquely named PNGs')
            source_dir = job_dir / 'animation' / 'uploads' / 'multi' / f'scene_{cutout_scene:02d}' / multi_id
            source_dir.mkdir(parents=True, exist_ok=True)
            for upload in multi_uploads:
                raw = upload.getvalue()
                if not raw or len(raw) > 20 * 1024 * 1024:
                    raise ValueError('Each puppet PNG must be under 20 MB')
                with _PILImage.open(_BytesIO(raw)) as img:
                    img.load()
                    if 'A' not in img.getbands() and 'transparency' not in img.info:
                        raise ValueError(f'{upload.name} needs a transparent background')
                    img.save(source_dir / upload.name, format='PNG')
            stage_character(job_dir, cutout_scene, multi_id, source_dir,
                            x=multi_x, y=multi_y, scale=multi_scale, depth=multi_depth)
            st.success(f'Staged {multi_id}; not yet approved for rendering.')
            st.rerun()
        except Exception as exc:
            st.error(f'Character import failed: {exc}')

    if multi_draft:
        characters = multi_draft['characters']
        st.markdown('**Staged characters**')
        st.dataframe([{'id': c['id'], 'x': c['x'], 'y': c['y'],
                       'scale': c['scale'], 'depth': c['depth'],
                       'parts': len(c['parts'])} for c in characters],
                     hide_index=True, use_container_width=True)
        if characters:
            selected_id = st.selectbox('Edit character joints', [c['id'] for c in characters],
                                       key=f'multi_joint_character_{cutout_scene}')
            selected_char = next(c for c in characters if c['id'] == selected_id)
            with st.expander('Joint positions, parents and pivots'):
                joint_rows = [
                    {'id': p['id'], 'parent': p.get('parent') or '',
                     'x': p['x'], 'y': p['y'], 'width': p['width'],
                     'pivot_x': p['pivot'][0], 'pivot_y': p['pivot'][1], 'z': p['z']}
                    for p in selected_char['parts']
                ]
                edited = st.data_editor(joint_rows, hide_index=True,
                                        disabled=['id'], num_rows='fixed',
                                        use_container_width=True,
                                        key=f'multi_joints_{cutout_scene}_{selected_id}')
                if st.button('Save staged joints', key=f'multi_save_joints_{cutout_scene}'):
                    try:
                        rows = edited.to_dict('records') if hasattr(edited, 'to_dict') else edited
                        update_character_joints(job_dir, cutout_scene, selected_id, rows)
                        st.success('Staged joint adjustments saved.')
                        st.rerun()
                    except Exception as exc:
                        st.error(f'Invalid joint changes: {exc}')
            if st.button('Remove selected staged character', key=f'multi_remove_{cutout_scene}'):
                remove_character(job_dir, cutout_scene, selected_id)
                st.rerun()

            st.markdown('**Add an action on the shared timeline**')
            col1, col2 = st.columns(2)
            with col1:
                action_character = st.selectbox('Actor', [c['id'] for c in characters],
                                                key=f'multi_actor_{cutout_scene}')
                action_motion = st.selectbox('Motion clip', available_motions(job_dir),
                                             key=f'multi_motion_{cutout_scene}')
                action_start = st.number_input('Start (seconds)', min_value=0.,
                                               max_value=120., value=0., step=.25,
                                               key=f'multi_start_{cutout_scene}')
                action_duration = st.number_input('Duration (seconds)', min_value=.1,
                                                  max_value=120., value=min(2., float(multi_duration)),
                                                  step=.25, key=f'multi_duration_{cutout_scene}')
            with col2:
                action_repeat = st.number_input('Repeat cycles', min_value=1, max_value=12,
                                                value=1, key=f'multi_repeat_{cutout_scene}')
                action_intensity = st.slider('Intensity', min_value=.1, max_value=2.,
                                             value=1., step=.1, key=f'multi_intensity_{cutout_scene}')
                action_direction = st.selectbox('Travel direction', [1, -1],
                                                format_func=lambda d: 'Right' if d == 1 else 'Left',
                                                key=f'multi_direction_{cutout_scene}')
                action_distance = st.number_input('Travel (canvas widths)', min_value=0.,
                                                  max_value=2., value=.15, step=.05,
                                                  key=f'multi_distance_{cutout_scene}')
            if st.button('Add motion to timeline', key=f'multi_action_add_{cutout_scene}'):
                try:
                    add_motion_action(job_dir, cutout_scene, character=action_character,
                                      motion=action_motion, start=action_start,
                                      duration=action_duration, repeat=action_repeat,
                                      intensity=action_intensity, direction=action_direction,
                                      distance=action_distance)
                    st.success('Action staged; different characters can act simultaneously.')
                    st.rerun()
                except Exception as exc:
                    st.error(f'Cannot add motion: {exc}')
        if multi_draft['timeline']:
            st.markdown('**Shared timeline**')
            st.dataframe([{'index': i, **a} for i, a in enumerate(multi_draft['timeline'])],
                         hide_index=True, use_container_width=True)
            remove_index = st.selectbox('Remove action index',
                                        list(range(len(multi_draft['timeline']))),
                                        key=f'multi_remove_action_index_{cutout_scene}')
            if st.button('Remove selected action', key=f'multi_remove_action_{cutout_scene}'):
                remove_motion_action(job_dir, cutout_scene, remove_index)
                st.rerun()
        left, right = st.columns(2)
        with left:
            if st.button('Preview staged scene (static)', key=f'multi_preview_{cutout_scene}'):
                try:
                    preview_multi_scene(job_dir, cutout_scene)
                    st.rerun()
                except Exception as exc:
                    st.error(f'Preview failed: {exc}')
        with right:
            if st.button('Approve multi-character scene', type='primary',
                         key=f'multi_approve_{cutout_scene}'):
                try:
                    approve_multi_scene(job_dir, cutout_scene)
                    st.success('Approved v3 scene, characters and motion timeline.')
                    st.rerun()
                except Exception as exc:
                    st.error(f'Approval failed: {exc}')
        preview_path = job_dir / 'animation' / 'multi_drafts' / f'scene_{cutout_scene:02d}' / 'preview.png'
        if preview_path.is_file():
            st.image(str(preview_path), width=270,
                     caption='Static bind-pose preview; render a short clip to inspect actual motion')
    else:
        st.info('No multi-character draft yet. Stage your first 12-part puppet above.')
    st.caption('Custom motion clips can be added as validated JSON in workspace/motions/. '
               'No natural-language motion planning, automatic rigging or collision detection yet.')

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

st.divider()
st.subheader('Step 3.5 · Blender preview and approval')
st.caption('Generate a lightweight 540×960 draft. The draft reuses existing narration and does not overwrite short.mp4.')
preview_file = job_dir / 'short_preview.mp4'
if st.button('Generate / refresh Blender preview'):
    try:
        cmd = [sys.executable, '-m', 'historyforgeai.cli', 'render',
               '--job', job_dir.name, '--visual-style', 'blender-2d', '--preview']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        if result.returncode:
            st.error(result.stderr[-3000:] or result.stdout[-3000:])
        else:
            st.success('Draft preview ready. Review every scene before approving.')
            st.rerun()
    except Exception as exc:
        st.error(f'Preview failed: {exc}')
if preview_file.is_file():
    st.video(str(preview_file))
    from historyforgeai.application.services.preview_approval import (
        preview_fingerprint, approve_preview, is_preview_approved,
    )
    try:
        current_fingerprint = preview_fingerprint(job_dir, plan)
        if is_preview_approved(job_dir, current_fingerprint):
            st.success('Preview approved for the current scene inputs')
        elif st.button('Approve current Blender preview'):
            approve_preview(job_dir, current_fingerprint)
            st.rerun()
        else:
            st.warning('Preview not approved. Review it before final rendering.')
    except Exception as exc:
        st.error(f'Preview approval check failed: {exc}')

st.caption('Full render overwrites short.mp4 and narration.wav. Back up existing files first.')
visual_style = st.selectbox('Video rendering style', ['cinematic', 'blender-2d'],
                            help='Blender 2D uses approved cutout layers, and requires Blender + FFmpeg installed.')
if visual_style == 'blender-2d':
    st.caption('Blender scenes without a cutout spec use their approved still-image background. '
               'Approve cutout drafts in Step 2.5 before rendering.')
confirm_render = st.checkbox('I verified that every numbered image matches its spoken narration and want to render')
if st.button('Render with selected narration', disabled=not confirm_render):
    try:
        cmd = [
            sys.executable, '-m', 'historyforgeai.cli', 'render',
            '--job', job_dir.name, '--generate-audio', '--scene-audio',
            '--motion', 'zoom_in', '--visual-style', visual_style,
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
            st.session_state['cinematic_use_music'] = True
            st.rerun()
        except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            st.error(f'Music import failed: {exc}')
    saved_music = find_background_music(job_dir)
    if saved_music:
        st.caption(f'Saved track: {saved_music.name}')
        st.audio(str(saved_music))
    st.session_state.setdefault('cinematic_use_music', bool(saved_music))
    use_music = st.checkbox(
        'Include saved background music',
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
