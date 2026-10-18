"""Optional Streamlit reviewer: launch with streamlit run .../storyboard_app.py -- JOB_DIR"""
import sys
from pathlib import Path
import streamlit as st
from historyforgeai.application.services.storyboard import load, save, apply_approved
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
for shot in board.shots:
    with st.expander(f'Scene {shot.scene_index}: {shot.narration[:90]}',expanded=True):
        st.write(shot.narration)
        st.caption(shot.visual_description)
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
