import json
import re
from pathlib import Path
from historyforgeai.domain.models import Job, JobStatus
from historyforgeai.application.services.job_ids import new_job_id
from historyforgeai.application.services.timeline import build_timeline
from historyforgeai.application.services.visuals import VisualResolver
from historyforgeai.infrastructure.persistence.characters import CharacterRegistry
import subprocess
import shutil

class ShortsPipeline:
    def __init__(self, repo, llm, research, assets, speech, renderer, workspace: Path):
        self.repo, self.llm, self.research, self.assets = repo, llm, research, assets
        self.speech, self.renderer, self.workspace = speech, renderer, workspace

    def run(self, topic: str, duration=48, scenes=6, fetch_assets=False, synthesize_audio=True,
            render=True, research_enabled=False, scene_audio=False, motion="zoom_in"):
        job = Job(id=new_job_id(topic, self.workspace / 'jobs'), topic=topic)
        self.repo.save(job)
        folder = self.workspace / "jobs" / job.id
        try:
            context = self.research.collect(topic) if research_enabled else "No external sources retrieved."
            (folder / "research_notes.txt").write_text(context, encoding="utf-8")
            plan = self.llm.create_plan(topic, context, duration, scenes)
            if len(plan.scenes) != scenes:
                raise ValueError(f"Expected {scenes} scenes, received {len(plan.scenes)}")
            actual = sum(s.duration_seconds for s in plan.scenes)
            if abs(actual-duration) > 1.0:
                raise ValueError(f"Scene durations total {actual:.2f}, expected {duration}")
            job.status = JobStatus.PLANNED
            if fetch_assets:
                for scene in plan.scenes:
                    destination = folder / "assets" / f"scene_{scene.index:02d}.jpg"
                    meta = self.assets.fetch(scene.asset_query, str(destination))
                    if meta:
                        scene.image_path = str(destination)
                        scene.asset_source_url = meta.get("source_url")
                        scene.asset_license = meta.get("license")
                        scene.attribution = meta.get("attribution")
                job.status = JobStatus.ASSETS_READY
            VisualResolver(CharacterRegistry(self.workspace / "characters")).resolve(plan)
            plan_path = folder / "scene_plan.json"
            plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
            job.plan_path = str(plan_path)
            self.repo.save(job)
            if render:
                audio = None
                measured = None
                if synthesize_audio and scene_audio:
                    if not shutil.which('ffprobe') or not shutil.which('ffmpeg'):
                        raise RuntimeError('ffmpeg and ffprobe are required')
                    durations = []
                    parts = []
                    for scene in plan.scenes:
                        dest = folder / f'narration_scene_{scene.index:02d}.wav'
                        if not self.speech.synthesize(scene.narration, str(dest)):
                            raise RuntimeError('Speech generation failed for scene ' + str(scene.index))
                        probe = subprocess.check_output(['ffprobe','-v','error','-show_entries',
                            'format=duration','-of','default=noprint_wrappers=1:nokey=1',str(dest)], text=True)
                        duration = float(probe.strip()) + 0.25
                        padded = folder / f'narration_padded_{scene.index:02d}.wav'
                        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(dest),
                            '-af',f'apad=whole_dur={duration:.3f}','-t',f'{duration:.3f}',
                            '-ar','24000','-ac','1',str(padded)], check=True)
                        durations.append(duration)
                        parts.append(padded)
                    for scene, length in zip(plan.scenes, durations):
                        scene.duration_seconds = length
                    measured = durations
                    audio_list = folder / 'audio_concat.txt'
                    audio_list.write_text(''.join(f"file '{p.resolve()}'\n" for p in parts), encoding='utf-8')
                    audio = str(folder / 'narration.wav')
                    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat',
                        '-safe','0','-i',str(audio_list),'-ar','24000','-ac','1',audio], check=True)
                elif synthesize_audio:
                    dest = folder / 'narration.wav'
                    if self.speech.synthesize(plan.narration, str(dest)):
                        audio = str(dest)
                (folder / 'timeline.json').write_text(json.dumps(build_timeline(plan, measured), indent=2), encoding='utf-8')
                plan_path.write_text(plan.model_dump_json(indent=2), encoding='utf-8')
                job.video_path = self.renderer.render(plan, str(folder), audio, motion=motion)
                job.status = JobStatus.RENDERED
            self.repo.save(job)
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.errors.append(f"{type(exc).__name__}: {exc}")
            self.repo.save(job)
            raise
        return job
