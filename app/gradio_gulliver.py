
import json
import asyncio

from src.config import UserConfig
from app.abus_downloader import *
from app.abus_path import *
from app.abus_ffmpeg import *
from app.abus_demucs import *
from app.abus_genuine import *
from app.abus_files import *

from app.abus_asr_parameters import *
from app.abus_asr_faster_whisper import *
from app.abus_asr_whisper import *
from app.abus_asr_whisper_timestamped import *
from app.abus_asr_whisperx import *

from app.abus_translate_deep import *
from app.abus_translate_azure import *

from app.abus_voice_ms import *
from app.abus_voice_celeb import *
from app.abus_voice_kokoro import *

from app.abus_tts_azure import *
from app.abus_tts_edge import *
from app.abus_tts_f5 import *
from app.abus_tts_cosyvoice import *
from app.abus_tts_kokoro import *
from app.abus_hf import AbusHuggingFace
from app.abus_lipsync import LipSyncRunner
from app.abus_pipeline import YoutubePipelineParams, YoutubePipelineResult


import src.ui as ui
from src.i18n.i18n import I18nAuto
i18n = I18nAuto()

import structlog
logger = structlog.get_logger()


class GradioGulliver:
    def __init__(self, user_config: UserConfig):
        self.user_config = user_config
        
        self.fm = FileManager()

        self.downloader = YoutubeDownloader()
        self.ms_voice_manager = MSVoiceManager(self.user_config.get('ms_language', "English"))
        self.edge_tts = AzureTTS() if azure_text_api_working() else EdgeTTS()
        
        self.f5_tts = None
        self.cosy_tts = None
        
        self.kokoro_tts = None
        self.kokoro_vm = None

        self.translator = AzureTranslator() if azure_text_api_working() == True else DeepTranslator()
        self.lipsync = LipSyncRunner(self.user_config)
        self.last_lipsync_status = ""
        
        asr_engine = self.user_config.get("asr_engine", 'faster-whisper')
        self.whisper_inf = self.switch_case(asr_engine)   

        
        # self.mdxnet_models_dir = os.path.join(os.getcwd(), 'model', 'mdxnet-model')
        # with open(os.path.join(self.mdxnet_models_dir, 'model_data.json')) as infile:
        #     self.mdx_model_params = json.load(infile)

    def switch_case(self, case):
        switch_dict = {
            'faster-whisper': lambda: FasterWhisperInference(),
            'whisper': lambda: WhisperInference(),
            'whisper-timestamped': lambda: WhisperTimestampedInference(),
            'whisperX': lambda: WhisperXInference()
        }
        return switch_dict.get(case, lambda: FasterWhisperInference())()    
            
            
    def gradio_workspace_folder(self):
        cmd_open_explorer(path_workspace_folder())
    
    def gradio_temp_folder(self):
        cmd_open_explorer(path_gradio_folder())
    
    
    def get_asr_engines(self):
        return ['faster-whisper', 'whisper', 'whisper-timestamped', 'whisperX']
    
    def update_whisper_models(self, asr_engine):
        whisper_inf = self.switch_case(asr_engine)       
        model_list = whisper_inf.available_models()
        if len(model_list) > 0:
            model_name = self.user_config.get(f'{asr_engine.replace("-", "_")}_model', 'large')
            return gr.update(choices=model_list, value=model_name)
        
        return gr.update(choices=[], value=None)

                    
    def get_whisper_models(self):
        return self.whisper_inf.available_models()
        
    def get_whisper_languages(self):
        return self.whisper_inf.available_langs()

    def get_whisper_compute_types(self):
        return FasterWhisperInference.available_compute_types()

    def get_lipsync_engines(self):
        return LipSyncRunner.available_engines()

    def _get_f5_tts(self):
        if self.f5_tts is None:
            self.f5_tts = F5TTS()
        return self.f5_tts

    def _get_cosy_tts(self):
        if self.cosy_tts is None:
            self.cosy_tts = CosyVoiceInference()
        return self.cosy_tts

    def _get_kokoro_tts(self):
        if self.kokoro_tts is None:
            self.kokoro_tts = KokoroTTS()
        return self.kokoro_tts

    def _get_kokoro_voice_manager(self):
        if self.kokoro_vm is None:
            self.kokoro_vm = KokoroVoiceManager()
        return self.kokoro_vm
            
    # return Video, Audio, File    
    def gradio_upload_source(self, 
                      file_obj, mic_file, youtube_url: str, video_quality: str, audio_format: str, clip_seconds: float = None, clip_start_seconds: float = 0):
        
        self.user_config.set("video_quality", video_quality)
        self.user_config.set("audio_format", audio_format)

        try:
            logger.debug(f'upload_source: file_obj={file_obj}, mic_file={mic_file}, youtube_url={youtube_url}')          
            self.fm = FileManager()           
            if self._upload(file_obj, mic_file, youtube_url, video_quality, audio_format, clip_seconds, clip_start_seconds) == False:
                return None, None, None
                            
            source_audio = self.fm.get_split("Source.audio")           
            if(self.has_video and ffmpeg_browser_compatible(self.source_file)):
                return self.source_file, source_audio, self.fm.get_all_files()
            else:
                return None, source_audio, self.fm.get_all_files()
        except Exception as e:
            logger.error(f"[gradio_gulliver.py] gradio_upload_source - Error transcribing file: {e}")
            gr.Warning(f'{e}')
            return None, None, None    
        

    def _upload(self,
                file_obj, mic_file, youtube_url: str, video_quality: str, audio_format: str, clip_seconds: float = None, clip_start_seconds: float = 0):
        if (file_obj is not None):
            uploaded_file = cmd_copy_file_to(file_obj.name, path_workspace_subfolder(file_obj.name))
        elif mic_file and mic_file.strip():
            uploaded_file = cmd_copy_file_to(mic_file, path_workspace_subfolder(mic_file))
        elif youtube_url and youtube_url.strip():
            youtube_file = self.downloader.yt_download(youtube_url, path_youtube_folder(), video_quality)
            uploaded_file = cmd_copy_file_to(youtube_file, path_workspace_subfolder(youtube_file))
        else:
            return False

        if clip_seconds and clip_seconds > 0:
            clip_label = str(clip_seconds).replace(".", "p")
            start_label = str(clip_start_seconds or 0).replace(".", "p")
            clipped_file = path_add_postfix(uploaded_file, f"_clip_{start_label}s_{clip_label}s")
            ffmpeg_trim_seconds(uploaded_file, clipped_file, clip_seconds, clip_start_seconds or 0)
            if not os.path.exists(clipped_file):
                raise RuntimeError(f"Failed to trim media to {clip_seconds} seconds.")
            uploaded_file = clipped_file
        
        self.source_file = uploaded_file
        
        self.has_audio, self.has_video = ffmpeg_codec_type(self.source_file)
        logger.debug(f'upload_source: source_file={self.source_file}, has_audio={self.has_audio}, has_video={self.has_video}')
        if self.has_audio == False:     # error
            return False
        elif self.has_video == False:   # audio-only
            self.fm.set_split("Source.video", None)
            self.fm.set_split("Source.audio", self.source_file)   
        else:
            input_audio_file = path_change_ext(self.source_file, f'.{audio_format}')
            ffmpeg_extract_audio(self.source_file, input_audio_file, audio_format)    
            self.fm.set_split("Source.video", self.source_file)
            self.fm.set_split("Source.audio", input_audio_file)
        return True     


    def gradio_youtube_pipeline(self,
                                youtube_url: str, video_quality: str, audio_format: str,
                                asr_engine, modelName, whisper_language, compute_type, denoise_level,
                                source_lang, target_lang,
                                voice_name: str, semitones, speed_factor, volume_factor,
                                lip_sync_enabled, lip_sync_engine, lip_sync_bbox_shift, lip_sync_allow_fallback):
        try:
            result = self.run_youtube_pipeline(
                YoutubePipelineParams(
                    youtube_url=youtube_url,
                    video_quality=video_quality,
                    audio_format=audio_format,
                    asr_engine=asr_engine,
                    asr_model=modelName,
                    media_language=whisper_language,
                    compute_type=compute_type,
                    denoise_level=denoise_level,
                    source_language=source_lang,
                    target_language=target_lang,
                    voice_name=voice_name,
                    pitch=semitones,
                    speech_rate=speed_factor,
                    volume=volume_factor,
                    lip_sync_enabled=lip_sync_enabled,
                    lip_sync_engine=lip_sync_engine,
                    lip_sync_bbox_shift=lip_sync_bbox_shift,
                    lip_sync_allow_fallback=lip_sync_allow_fallback,
                )
            )
            return result.as_gradio_outputs()
        except Exception as e:
            logger.error(f"[gradio_gulliver.py] gradio_youtube_pipeline - Error: {e}")
            gr.Warning(f'{e}')
            result = YoutubePipelineResult(
                input_video=self.fm.get_split("Source.video"),
                input_audio=self.fm.get_split("Source.audio"),
                files=self.fm.get_all_files(),
                status="Pipeline failed: " + str(e),
                ok=False,
                error=str(e),
            )
            return result.as_gradio_outputs()

    def run_youtube_pipeline(self, params: YoutubePipelineParams) -> YoutubePipelineResult:
        status = []
        self.last_lipsync_status = ""

        if not params.youtube_url or not params.youtube_url.strip():
            raise ValueError("YouTube URL is required for the full pipeline.")

        self.lipsync.preflight(
            params.lip_sync_engine,
            enabled=params.lip_sync_enabled,
            allow_audio_only_fallback=params.lip_sync_allow_fallback,
        )

        input_video, input_audio, _ = self.gradio_upload_source(
            None, None, params.youtube_url, params.video_quality, params.audio_format, params.clip_seconds, params.clip_start_seconds
        )
        if not input_audio and not self.fm.get_split("Source.audio"):
            raise RuntimeError("Source media download or audio extraction failed.")
        status.append("1/5 Downloaded source media.")

        if params.bootstrap_assets:
            self._bootstrap_pipeline_assets(params.tts_strategy)

        input_video, input_audio, transcription_text, _ = self.gradio_whisper(
            params.asr_engine,
            params.asr_model,
            params.media_language,
            params.compute_type,
            params.denoise_level,
        )
        if not transcription_text:
            raise RuntimeError("Transcription did not produce subtitles or text.")
        status.append("2/5 Transcribed source speech.")

        _, _, translation_text, _ = self.gradio_translate(
            params.source_language,
            transcription_text,
            params.target_language,
        )
        if not translation_text:
            raise RuntimeError("Translation did not produce output text.")
        status.append(f"3/5 Translated subtitles: {params.source_language} -> {params.target_language}.")

        selected_voice = self._voice_for_target_language(params.target_language, params.voice_name)
        dubbing_video, dubbing_audio, files, tts_label = self._run_pipeline_dubbing(
            params,
            translation_text,
            selected_voice,
        )
        if not dubbing_audio:
            raise RuntimeError("Target speech synthesis did not produce audio.")
        if self.fm.get_split("Source.video") and not dubbing_video:
            raise RuntimeError("Dubbed video generation did not produce a video file.")
        status.append(f"4/5 Synthesized target speech with {tts_label}.")

        if self.last_lipsync_status:
            status.append(f"5/5 {self.last_lipsync_status}")
        else:
            status.append("5/5 Final dubbed video generated.")

        return YoutubePipelineResult(
            input_video=input_video or self.fm.get_split("Source.video"),
            input_audio=input_audio or self.fm.get_split("Source.audio"),
            transcription_text=transcription_text,
            output_video=dubbing_video,
            output_audio=dubbing_audio,
            translation_text=translation_text,
            files=self.fm.get_all_files() if files is None else files,
            status="\n".join(status),
        )
    

    def gradio_whisper_default(self):
        return ["large", "english", "float16", 0]

    # return Video, Audio, File    
    def gradio_whisper(self, 
                      asr_engine, modelName, whisper_language, compute_type, denoise_level):
        
        self.user_config.set("asr_engine", asr_engine)
        self.user_config.set(f'{asr_engine.replace("-", "_")}_model', modelName)
        self.user_config.set("whisper_language", whisper_language)
        self.user_config.set("whisper_compute_type", compute_type)
        self.user_config.set("denoise_level", denoise_level)          
        
        try:                          
            source_audio = self.fm.get_split("Source.audio")
            denoise_inst_path, denoise_vocal_path = self._denoise(source_audio, denoise_level)
            input_path = denoise_vocal_path if os.path.exists(denoise_vocal_path) else source_audio

            params = WhisperParameters(model_size=modelName, 
                                       lang=whisper_language.lower(), 
                                       compute_type=compute_type)   
            
            self.whisper_inf = self.switch_case(asr_engine)                            
            subtitles = self.whisper_inf.transcribe_file(input_path, params, False, gr.Progress())  # highlight_words=False
            self.fm.set_subtitles(subtitles, whisper_language, source_audio) 
            srt_file = self.fm.get_subtitle('.srt')
            srt_string = self._read_file(srt_file)
            logger.debug(f'srt_file = {srt_file}, self.source_file = {self.source_file}')
            
            if(self.has_video and ffmpeg_browser_compatible(self.source_file)):
                if srt_file:
                    return (self.source_file, srt_file), source_audio, srt_string, self.fm.get_all_files()
                else:
                    return self.source_file, source_audio, srt_string, self.fm.get_all_files()
            else:
                return None, source_audio, srt_string, self.fm.get_all_files()
        except Exception as e:
            logger.error(f"[gradio_gulliver.py] gradio_upload_source - Error transcribing file: {e}")
            gr.Warning(f'{e}')
            return None, None, None, None    

    
    # return inst, vocal    
    def _denoise(self, source_audio, denoise_level=2):
        if denoise_level == 1:
            return self._demucs_htdemucs(source_audio)
        elif denoise_level ==2:
            return self._demucs_htdemucs_ft(source_audio)
        else:
            return "", ""
                
        
            
    def _demucs_htdemucs(self, source_audio):
        _, extension = os.path.splitext(os.path.basename(source_audio))
        output_dir = os.path.dirname(source_audio)
        
        inst_audio_file, vocal_audio_file = demucs_split_file(source_audio, output_dir, 'htdemucs', extension[1:])
        self.fm.set_split("Instrumental.audio", inst_audio_file)
        self.fm.set_split("Vocals.audio", vocal_audio_file)

        return inst_audio_file, vocal_audio_file
    
    def _demucs_htdemucs_ft(self, source_audio):
        _, extension = os.path.splitext(os.path.basename(source_audio))
        output_dir = os.path.dirname(source_audio)
        
        inst_audio_file, vocal_audio_file = demucs_split_file(source_audio, output_dir, 'htdemucs_ft', extension[1:])
        self.fm.set_split("Instrumental.audio", inst_audio_file)
        self.fm.set_split("Vocals.audio", vocal_audio_file)

        return inst_audio_file, vocal_audio_file   


    # Translate
    def gradio_translate_languages(self):
        return self.translator.get_languages()
    
    
    def gradio_language_detection(self,
                                  transcription_text):
        languageName = AbusText.detect_language_name(transcription_text[:200])
        return languageName
                                        
    
    def gradio_translate(self,
                        source_lang, transcription_text, target_lang):
        if len(transcription_text) < 1:
            logger.warning(f"[gradio_gulliver.py] gradio_translate - no actions")
            return None, None, None, self.fm.get_all_files() 
        
        self.user_config.set("translate_source_language", source_lang)            
        self.user_config.set("translate_target_language", target_lang)    

        transcription_file = None
        if self._is_subtitle_format(transcription_text):
            subs = pysubs2.SSAFile.from_string(transcription_text)
            transcription_file = os.path.join(path_translate_folder(), path_new_filename(f".{subs.format}"))
            subs.save(transcription_file)

        translation_file = None
        translation_text = None
        if transcription_file:
            translation_file = self._translate_subtitle(transcription_file, source_lang, target_lang)
        else:
            translation_text = self._translate_text(transcription_text, source_lang, target_lang)

        source_video_file = self.fm.get_split("Source.video")
        source_audio_file = self.fm.get_split("Source.audio")
        
        output_video_path = (source_video_file, translation_file) if source_video_file and translation_file else source_video_file
        output_audio_path = source_audio_file
        output_translation_text = self._read_file(translation_file) if translation_file else translation_text
        return output_video_path, output_audio_path, output_translation_text, self.fm.get_all_files()    
                           

    def _read_file(self, filepath):    
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read()
            return content
        except UnicodeDecodeError:
            return "Error: The file is not a valid text file or uses an unsupported encoding."
        except IOError:
            return "Error: Unable to read the file."
        
        
    def _translate_subtitle(self, subtitle_file, source_lang, target_lang):
        try:
            translation_file = path_add_postfix(subtitle_file, f"_{target_lang}")
            self.translator.translate_file(source_lang, target_lang, subtitle_file, translation_file)
            
            target_lang_code = self.translator.get_language_code(target_lang)
            self.fm.set_translation(target_lang_code, translation_file)            
            return translation_file
        except Exception as e:
            logger.error(f"[gradio_gulliver.py] _translate_subtitle - error: {e}")
            gr.Warning(f'{e}')
            return None           

    def _translate_text(self, text, source_lang, target_lang):
        try:
            translated = self.translator.translate_text(source_lang, target_lang, text)
            return translated   
        except Exception as e:
            logger.error(f"[gradio_gulliver.py] _translate_text - error: {e}")
            gr.Warning(f'{e}')
            return None            


    # TTS
    
    def _is_subtitle_format(self, text):
        try:
            pysubs2.SSAFile.from_string(text)
            return True
        except Exception as e:
            return False     

    def _bootstrap_pipeline_assets(self, tts_strategy="source_voice"):
        AbusHuggingFace.initialize(app_name="voice")
        AbusHuggingFace.hf_download_models(file_type="edge-tts", level=0)
        AbusHuggingFace.hf_download_models(file_type="demucs", level=0)
        if str(tts_strategy).replace("-", "_") == "source_voice":
            AbusHuggingFace.hf_download_models(file_type="cosyvoice", level=0)

    def _voice_for_target_language(self, target_lang: str, current_voice: str):
        try:
            target_code = self.translator.get_language_code(target_lang)
            language_code = target_code.split("-")[0].split("_")[0]
            voices = self.ms_voice_manager.get_voices_with_code(language_code)
            if voices:
                return voices[0].getDisplayName()
        except Exception as e:
            logger.warning(f"[gradio_gulliver.py] _voice_for_target_language - fallback to selected voice: {e}")
        return current_voice

    def _lip_sync_video(self, mixed_audio_file, lip_sync_engine, lip_sync_bbox_shift, lip_sync_allow_fallback):
        source_video_file = self.fm.get_split("Source.video")
        if not source_video_file or not mixed_audio_file:
            self.last_lipsync_status = "Lip sync skipped because source video or dubbed audio is missing."
            return None

        output_file = path_add_postfix(source_video_file, f"_lipsync_{lip_sync_engine.replace(' ', '_')}", ".mp4")
        result = self.lipsync.run(
            source_video=source_video_file,
            audio_path=mixed_audio_file,
            output_path=output_file,
            engine=lip_sync_engine,
            bbox_shift=lip_sync_bbox_shift,
            enabled=True,
            allow_audio_only_fallback=lip_sync_allow_fallback,
        )
        self.last_lipsync_status = result.message
        self.fm.set_effect(f"{result.engine}.video", result.output_path)
        return result.output_path

    def _run_pipeline_dubbing(self, params: YoutubePipelineParams, translation_text: str, selected_voice: str):
        strategy = str(params.tts_strategy or "source_voice").replace("-", "_")
        if strategy == "source_voice":
            try:
                video, audio, files = self.gradio_source_voice_dubbing(
                    translation_text,
                    params.source_voice_engine,
                    params.source_voice_mode,
                    params.source_voice_speed,
                    params.audio_format,
                    params.lip_sync_enabled,
                    params.lip_sync_engine,
                    params.lip_sync_bbox_shift,
                    params.lip_sync_allow_fallback,
                )
                return video, audio, files, f"{params.source_voice_engine} source voice"
            except Exception as e:
                logger.error(f"[gradio_gulliver.py] source voice dubbing failed: {e}")
                if not params.allow_edge_tts_fallback:
                    raise
                gr.Warning(f"Source voice dubbing failed; falling back to Edge TTS: {e}")

        video, audio, files = self.gradio_edge_dubbing(
            translation_text,
            selected_voice,
            params.pitch,
            params.speech_rate,
            params.volume,
            params.audio_format,
            params.lip_sync_enabled,
            params.lip_sync_engine,
            params.lip_sync_bbox_shift,
            params.lip_sync_allow_fallback,
        )
        return video, audio, files, selected_voice

    def gradio_source_voice_dubbing(
        self,
        translation_text,
        source_voice_engine="CosyVoice",
        source_voice_mode="Cross-Lingual",
        source_voice_speed=1.0,
        audio_format="mp3",
        lip_sync_enabled=False,
        lip_sync_engine=LipSyncRunner.ENGINE_DISABLED,
        lip_sync_bbox_shift=0,
        lip_sync_allow_fallback=True,
    ):
        if len(translation_text) < 1:
            logger.warning("[gradio_gulliver.py] gradio_source_voice_dubbing - no actions")
            return None, None, self.fm.get_all_files()

        if source_voice_engine != "CosyVoice":
            raise RuntimeError(f"Unsupported source voice engine: {source_voice_engine}")

        self.user_config.set("youtube_pipeline_tts_strategy", "source_voice")
        self.user_config.set("youtube_pipeline_source_voice_engine", source_voice_engine)
        self.user_config.set("youtube_pipeline_source_voice_mode", source_voice_mode)
        self.user_config.set("youtube_pipeline_source_voice_speed", source_voice_speed)
        self.user_config.set("audio_format", audio_format)
        self.user_config.set("lipsync_enabled", lip_sync_enabled)
        self.user_config.set("lipsync_engine", lip_sync_engine)
        self.user_config.set("lipsync_bbox_shift", lip_sync_bbox_shift)
        self.user_config.set("lipsync_allow_audio_only_fallback", lip_sync_allow_fallback)

        translation_file = None
        if self._is_subtitle_format(translation_text):
            subs = pysubs2.SSAFile.from_string(translation_text)
            translation_file = os.path.join(path_translate_folder(), path_new_filename(f".{subs.format}"))
            subs.save(translation_file)

        if translation_file:
            aidub_video_file, mixed_audio_file = self._source_voice_tts_subtitle(
                translation_file,
                source_voice_engine,
                source_voice_mode,
                source_voice_speed,
                audio_format,
            )
        else:
            aidub_video_file, mixed_audio_file = self._source_voice_tts_text(
                translation_text,
                source_voice_engine,
                source_voice_mode,
                source_voice_speed,
                audio_format,
            )

        if aidub_video_file and mixed_audio_file and lip_sync_enabled:
            try:
                lip_sync_video_file = self._lip_sync_video(
                    mixed_audio_file,
                    lip_sync_engine,
                    lip_sync_bbox_shift,
                    lip_sync_allow_fallback,
                )
                if lip_sync_video_file:
                    aidub_video_file = lip_sync_video_file
            except Exception as e:
                logger.error(f"[gradio_gulliver.py] gradio_source_voice_dubbing - lip sync failed: {e}")
                if not lip_sync_allow_fallback:
                    raise
                gr.Warning(f'{e}')

        output_video_path = (aidub_video_file, translation_file) if aidub_video_file and translation_file else aidub_video_file
        return output_video_path, mixed_audio_file, self.fm.get_all_files()

    def _source_voice_reference_audio(self, source_audio_file):
        _, vocal_audio_file = self._denoise(source_audio_file, 1)
        if vocal_audio_file and os.path.exists(vocal_audio_file):
            return self._source_voice_reference_clip(vocal_audio_file)
        return self._source_voice_reference_clip(source_audio_file)

    def _source_voice_reference_and_inst_audio(self, source_audio_file):
        inst_audio_file, vocal_audio_file = self._denoise(source_audio_file, 1)
        ref_audio_file = vocal_audio_file if vocal_audio_file and os.path.exists(vocal_audio_file) else source_audio_file
        ref_audio_file = self._source_voice_reference_clip(ref_audio_file)
        return ref_audio_file, inst_audio_file

    def _source_voice_reference_clip(self, ref_audio_file, max_seconds=25):
        if not ref_audio_file or not os.path.exists(ref_audio_file):
            return ref_audio_file
        duration = ffmpeg_get_duration(ref_audio_file)
        if duration <= 0 or duration <= max_seconds:
            return ref_audio_file

        clipped_ref_audio_file = path_add_postfix(ref_audio_file, f"_ref_{int(max_seconds)}s")
        ffmpeg_trim_seconds(ref_audio_file, clipped_ref_audio_file, max_seconds, 0)
        return clipped_ref_audio_file

    def _source_voice_tts_subtitle(self, subtitle_file, source_voice_engine, source_voice_mode, source_voice_speed, audio_format):
        source_audio_file = self.fm.get_split("Source.audio")
        if not source_audio_file:
            raise RuntimeError("Source audio is required for source voice dubbing.")

        ref_audio_file, inst_audio_file = self._source_voice_reference_and_inst_audio(source_audio_file)
        aidub_audio_file = path_add_postfix(source_audio_file, f"_{source_voice_engine}_source_voice")

        self._get_cosy_tts().srt_to_voice(
            subtitle_file,
            aidub_audio_file,
            ref_audio_file,
            "",
            source_voice_mode,
            float(source_voice_speed),
            audio_format,
        )

        return self._mix_source_voice_dubbing(
            source_audio_file,
            aidub_audio_file,
            inst_audio_file,
            source_voice_engine,
            audio_format,
        )

    def _source_voice_tts_text(self, text, source_voice_engine, source_voice_mode, source_voice_speed, audio_format):
        source_audio_file = self.fm.get_split("Source.audio")
        if not source_audio_file:
            raise RuntimeError("Source audio is required for source voice dubbing.")

        ref_audio_file, inst_audio_file = self._source_voice_reference_and_inst_audio(source_audio_file)
        aidub_audio_file = path_add_postfix(source_audio_file, f"_{source_voice_engine}_source_voice")

        self._get_cosy_tts().text_to_voice(
            text,
            aidub_audio_file,
            ref_audio_file,
            "",
            source_voice_mode,
            float(source_voice_speed),
            audio_format,
        )

        return self._mix_source_voice_dubbing(
            source_audio_file,
            aidub_audio_file,
            inst_audio_file,
            source_voice_engine,
            audio_format,
        )

    def _mix_source_voice_dubbing(self, source_audio_file, aidub_audio_file, inst_audio_file, source_voice_engine, audio_format):
        if not os.path.exists(aidub_audio_file):
            raise RuntimeError(f"Source voice TTS did not produce audio: {aidub_audio_file}")
        if not inst_audio_file or not os.path.exists(inst_audio_file):
            inst_audio_file, _ = self._denoise(source_audio_file, 1)

        mixed_audio_file = path_add_postfix(source_audio_file, f"_mixed_{source_voice_engine}_source_voice")
        ffmpeg_mix_audio(aidub_audio_file, inst_audio_file, mixed_audio_file, 0, 0, audio_format)
        self.fm.set_dubbing(f'{source_voice_engine}.source_voice.audio', aidub_audio_file)

        if self.has_video:
            source_video_file = self.fm.get_split("Source.video")
            aidub_video_file = path_add_postfix(source_video_file, f"_{source_voice_engine}_source_voice")
            ffmpeg_replace_audio(source_video_file, mixed_audio_file, aidub_video_file)
            self.fm.set_dubbing(f'{source_voice_engine}.source_voice.video', aidub_video_file)
            return aidub_video_file, mixed_audio_file
        return None, mixed_audio_file


           

    # Edge-TTS or Azure-TTS                             
    def gradio_edge_default(self):
        return [0, 0, 0]        
    
    def gradio_edge_dubbing(self, 
                            translation_text, voice_name: str, 
                            semitones, speed_factor, volume_factor, audio_format: str,
                            lip_sync_enabled=False, lip_sync_engine=LipSyncRunner.ENGINE_DISABLED,
                            lip_sync_bbox_shift=0, lip_sync_allow_fallback=True):
                         
        logger.debug(f"[gradio_gulliver.py] gradio_edge_dubbing - \
                    voice_name = {voice_name}, \
                    semitones = {semitones}, speed_factor = {speed_factor}, volume_factor = {volume_factor}, audio_format = {audio_format}")
        
        if len(translation_text) < 1:
            logger.warning(f"[gradio_gulliver.py] gradio_edge_dubbing - no actions")
            return None, None, self.fm.get_all_files() 
        
        self.user_config.set("edge_tts_pitch", semitones)     
        self.user_config.set("edge_tts_rate", speed_factor)
        self.user_config.set("edge_tts_volume", volume_factor)             
        self.user_config.set("audio_format", audio_format)
        self.user_config.set("lipsync_enabled", lip_sync_enabled)
        self.user_config.set("lipsync_engine", lip_sync_engine)
        self.user_config.set("lipsync_bbox_shift", lip_sync_bbox_shift)
        self.user_config.set("lipsync_allow_audio_only_fallback", lip_sync_allow_fallback)
        
        
        aidub_video_file = None
        mixed_audio_file = None                

        translation_file = None 
        if len(translation_text) > 0 and self._is_subtitle_format(translation_text):
            subs = pysubs2.SSAFile.from_string(translation_text)
            translation_file = os.path.join(path_translate_folder(), path_new_filename(f".{subs.format}"))
            subs.save(translation_file)   


        if translation_file:
            aidub_video_file, mixed_audio_file = self._edge_tts_subtitle(translation_file, 
                                                voice_name, semitones, speed_factor, volume_factor, audio_format)  
        elif translation_text:
            aidub_video_file, mixed_audio_file = self._edge_tts_text(translation_text, 
                                                voice_name, semitones, speed_factor, volume_factor, audio_format)

        if aidub_video_file and mixed_audio_file and lip_sync_enabled:
            try:
                lip_sync_video_file = self._lip_sync_video(
                    mixed_audio_file,
                    lip_sync_engine,
                    lip_sync_bbox_shift,
                    lip_sync_allow_fallback,
                )
                if lip_sync_video_file:
                    aidub_video_file = lip_sync_video_file
            except Exception as e:
                logger.error(f"[gradio_gulliver.py] gradio_edge_dubbing - lip sync failed: {e}")
                if not lip_sync_allow_fallback:
                    raise
                gr.Warning(f'{e}')

        output_video_path = (aidub_video_file, translation_file) if aidub_video_file and translation_file else aidub_video_file
        output_audio_path = mixed_audio_file
        return output_video_path, output_audio_path, self.fm.get_all_files()      
                            

    def _edge_tts_text(self, text: str, voice_name: str, semitones, speed_factor, volume_factor, audio_format: str):
        try:
            # TTS voice
            ms_voice = self.ms_voice_manager.get_voice(voice_name)
            target_language = ms_voice.getLanguageName()
                        
            # TTS
            source_audio_file = self.fm.get_split("Source.audio")                        
            aidub_audio_file = path_add_postfix(source_audio_file, f"_{target_language}")        
            
            self.edge_tts.text_to_voice(text, aidub_audio_file, ms_voice.name, semitones, speed_factor, volume_factor, audio_format)

            self.fm.set_dubbing(f'{voice_name}.audio', aidub_audio_file)           

            # Mix
            mixed_audio_file = path_add_postfix(source_audio_file, f"_mixed_{target_language}")            
            denoise_inst_path, _ = self._denoise(source_audio_file, 1)
            ffmpeg_mix_audio(aidub_audio_file, denoise_inst_path, mixed_audio_file, 0, 0, audio_format)
                                
            if self.has_video:
                source_video_file = self.fm.get_split("Source.video")
                aidub_video_file = path_add_postfix(source_video_file, f"_{target_language}")
                
                ffmpeg_replace_audio(source_video_file, mixed_audio_file, aidub_video_file)
                
                self.fm.set_dubbing(f'{voice_name}.video', aidub_video_file)
                return aidub_video_file, mixed_audio_file
            else:
                return None, mixed_audio_file, 
        except Exception as e:
            logger.error(f"[gradio_gulliver.py] _edge_tts_text - Error : {e}")
            gr.Warning(f'{e}')
            return None, None    

    
    
    def _edge_tts_subtitle(self, 
                           subtitle_file, voice_name: str, semitones, speed_factor, volume_factor, audio_format: str):
        logger.debug(f"[gradio_gulliver.py] _edge_tts_subtitle - subtitle_file = {subtitle_file}, voice_name = {voice_name}, \
                     semitones = {semitones}, speed_factor = {speed_factor}, volume_factor = {volume_factor}, audio_format = {audio_format}")
        
        try:
            # TTS voice
            ms_voice = self.ms_voice_manager.get_voice(voice_name)
            target_language = ms_voice.getLanguageName()
                        
            # TTS
            source_audio_file = self.fm.get_split("Source.audio")                        
            aidub_audio_file = path_add_postfix(source_audio_file, f"_{target_language}")        
            
            self.edge_tts.srt_to_voice(subtitle_file, aidub_audio_file, ms_voice.name, semitones, speed_factor, volume_factor, audio_format)

            self.fm.set_dubbing(f'{voice_name}.audio', aidub_audio_file)           
        
            # Mix
            mixed_audio_file = path_add_postfix(source_audio_file, f"_mixed_{target_language}")            
            denoise_inst_path, _ = self._denoise(source_audio_file, 1)
            ffmpeg_mix_audio(aidub_audio_file, denoise_inst_path, mixed_audio_file, 0, 0, audio_format)
                                
            if self.has_video:
                source_video_file = self.fm.get_split("Source.video")
                aidub_video_file = path_add_postfix(source_video_file, f"_{target_language}")
                
                ffmpeg_replace_audio(source_video_file, mixed_audio_file, aidub_video_file)
                
                self.fm.set_dubbing(f'{voice_name}.video', aidub_video_file)
                return aidub_video_file, mixed_audio_file
            else:
                return None, mixed_audio_file
        except Exception as e:
            logger.error(f"[gradio_gulliver.py] _edge_tts_subtitle - Error : {e}")
            gr.Warning(f'{e}')
            return None, None 


    # F5-TTS

    def gradio_f5_default(self):
        return ["SWivid/F5-TTS_v1", 1.0]
    
    def gradio_f5_available_models(self):
        return self._get_f5_tts().available_models()


    def gradio_f5_dubbing_single(self, 
                                 translation_text, 
                                 celeb_name, celeb_audio, celeb_transcript, 
                                 model_choice, speed_factor, audio_format: str):
        
        logger.debug(f"[gradio_gulliver.py] gradio_f5_dubbing_single - \
                    celeb_name = {celeb_name}, celeb_audio = {celeb_audio}, \
                    model_choice = {model_choice}, speed_factor = {speed_factor}, audio_format = {audio_format}")
        
        if len(translation_text) < 1:
            logger.warning(f"[gradio_gulliver.py] gradio_f5_dubbing_single - no actions")
            return None, None, self.fm.get_all_files() 
        
            
        translation_file = None 
        if len(translation_text) > 0 and self._is_subtitle_format(translation_text):
            subs = pysubs2.SSAFile.from_string(translation_text)
            translation_file = os.path.join(path_translate_folder(), path_new_filename(f".{subs.format}"))
            subs.save(translation_file)                    
                

        aidub_video_file = None
        mixed_audio_file = None                

        if translation_file:
            aidub_video_file, mixed_audio_file = self._f5_tts_single(self._read_file(translation_file), 
                                                celeb_name, celeb_audio, celeb_transcript, model_choice, speed_factor, audio_format)
        elif translation_text:
            aidub_video_file, mixed_audio_file = self._f5_tts_single(translation_text, 
                                                celeb_name, celeb_audio, celeb_transcript, model_choice, speed_factor, audio_format)

        output_video_path = (aidub_video_file, translation_file) if aidub_video_file and translation_file else aidub_video_file
        output_audio_path = mixed_audio_file
        return output_video_path, output_audio_path, self.fm.get_all_files()                   
                  
        
       
    def _f5_tts_single(self, text:str, celeb_name, celeb_audio, celeb_transcript, model_choice, speed_factor, audio_format: str):
        logger.debug(f"[gradio_gulliver.py] _f5_tts_single - text = {text}, \
                    celeb_name = {celeb_name}, celeb_audio = {celeb_audio}, \
                    model_choice = {model_choice}, speed_factor = {speed_factor}, audio_format = {audio_format}")     
                
        try:
            # F5-TTS
            source_audio_file = self.fm.get_split("Source.audio")           
            aidub_audio_file = path_add_postfix(source_audio_file, f"_{celeb_name}")                               
            self._get_f5_tts().infer_single(text.strip(), aidub_audio_file, celeb_audio, celeb_transcript, model_choice, speed_factor, audio_format)
            
            # Mix
            mixed_audio_file = path_add_postfix(source_audio_file, f"_mixed_{celeb_name}")            
            denoise_inst_path, _ = self._denoise(source_audio_file, 1)
            ffmpeg_mix_audio(aidub_audio_file, denoise_inst_path, mixed_audio_file, 0, 0, audio_format)
            self.fm.set_dubbing(f'{celeb_name}.audio', aidub_audio_file)
                                
            if self.has_video:
                source_video_file = self.fm.get_split("Source.video")
                aidub_video_file = path_add_postfix(source_video_file, f"_{celeb_name}")
                
                ffmpeg_replace_audio(source_video_file, mixed_audio_file, aidub_video_file)
                self.fm.set_dubbing(f'{celeb_name}.video', aidub_video_file)
                return aidub_video_file, mixed_audio_file
            else:
                return None, mixed_audio_file
        except Exception as e:
            logger.error(f"[gradio_gulliver.py] _f5_tts_single - Error : {e}")
            gr.Warning(f'{e}')
            return None, None    
    
    
    # Cosy-Voice
    
    def gradio_cosy_default(self):
        return ["Zero-Shot", 1.0]    
        
    def gradio_cosy_dubbing(self, 
                        translation_text, 
                        celeb_name, celeb_audio, celeb_transcript, 
                        mode_choice, speed_factor, audio_format: str):
        if len(translation_text) < 1:
            logger.warning(f"[gradio_gulliver.py] gradio_f5_dubbing_single - no actions")
            return None, None, self.fm.get_all_files() 
        
            
        translation_file = None 
        if len(translation_text) > 0 and self._is_subtitle_format(translation_text):
            subs = pysubs2.SSAFile.from_string(translation_text)
            translation_file = os.path.join(path_translate_folder(), path_new_filename(f".{subs.format}"))
            subs.save(translation_file)                    
                

        aidub_video_file = None
        mixed_audio_file = None   
                
        if translation_file:
            aidub_video_file, mixed_audio_file = self._cosy_tts_single(self._read_file(translation_file), 
                                                celeb_name, celeb_audio, celeb_transcript, mode_choice, speed_factor, audio_format)
        elif translation_text:
            aidub_video_file, mixed_audio_file = self._cosy_tts_single(translation_text, 
                                                celeb_name, celeb_audio, celeb_transcript, mode_choice, speed_factor, audio_format)

        output_video_path = (aidub_video_file, translation_file) if aidub_video_file and translation_file else aidub_video_file
        output_audio_path = mixed_audio_file
        return output_video_path, output_audio_path, self.fm.get_all_files()        

   
    
    def _cosy_tts_single(self, text:str, celeb_name, celeb_audio, celeb_transcript, mode_choice, speed_factor, audio_format: str):
        logger.debug(f"[gradio_gulliver.py] _cosy_tts_single - text = {text}, \
                    celeb_name = {celeb_name}, celeb_audio = {celeb_audio}, \
                    mode_choice = {mode_choice}, speed_factor = {speed_factor}, audio_format = {audio_format}")     
                
        try:
            # F5-TTS
            source_audio_file = self.fm.get_split("Source.audio")           
            aidub_audio_file = path_add_postfix(source_audio_file, f"_{celeb_name}")                               
            self._get_cosy_tts().infer_single(text.strip(), aidub_audio_file, celeb_audio, celeb_transcript, mode_choice, speed_factor, audio_format)
            
            # Mix
            mixed_audio_file = path_add_postfix(source_audio_file, f"_mixed_{celeb_name}")            
            denoise_inst_path, _ = self._denoise(source_audio_file, 1)
            ffmpeg_mix_audio(aidub_audio_file, denoise_inst_path, mixed_audio_file, 0, 0, audio_format)
            self.fm.set_dubbing(f'{celeb_name}.audio', aidub_audio_file)
                                
            if self.has_video:
                source_video_file = self.fm.get_split("Source.video")
                aidub_video_file = path_add_postfix(source_video_file, f"_{celeb_name}")
                
                ffmpeg_replace_audio(source_video_file, mixed_audio_file, aidub_video_file)
                self.fm.set_dubbing(f'{celeb_name}.video', aidub_video_file)
                return aidub_video_file, mixed_audio_file
            else:
                return None, mixed_audio_file
        except Exception as e:
            logger.error(f"[gradio_gulliver.py] _cosy_tts_single - Error : {e}")
            gr.Warning(f'{e}')
            return None, None    
       
       
       
    # kokoro    
        
    def gradio_kokoro_default(self):
        return [1, "mp3"]
    
    def gradio_kokoro_dubbing(self, 
                            translation_text, language_name, voice_name: str, 
                            speed_factor, audio_format: str):
                         
        logger.debug(f"[gradio_gulliver.py] gradio_kokoro_dubbing - \
                    language_name = {language_name}, voice_name = {voice_name}, \
                    speed_factor = {speed_factor}, audio_format = {audio_format}")
        
        if len(translation_text) < 1:
            logger.warning(f"[gradio_gulliver.py] gradio_kokoro_dubbing - no actions")
            return None, None, self.fm.get_all_files() 
        
        # self.user_config.set("edge_tts_rate", speed_factor)  
        self.user_config.set("audio_format", audio_format)
        
        
        aidub_video_file = None
        mixed_audio_file = None                

        translation_file = None 
        if len(translation_text) > 0 and self._is_subtitle_format(translation_text):
            subs = pysubs2.SSAFile.from_string(translation_text)
            translation_file = os.path.join(path_translate_folder(), path_new_filename(f".{subs.format}"))
            subs.save(translation_file)   


        if translation_file:
            aidub_video_file, mixed_audio_file = self._kokoro_tts_subtitle(translation_file, 
                                                language_name, voice_name, speed_factor, audio_format)  
        elif translation_text:
            aidub_video_file, mixed_audio_file = self._kokoro_tts_text(translation_text, 
                                                language_name, voice_name, speed_factor, audio_format)
        
        
        output_video_path = (aidub_video_file, translation_file) if aidub_video_file and translation_file else aidub_video_file
        output_audio_path = mixed_audio_file
        return output_video_path, output_audio_path, self.fm.get_all_files()        
                     
        
    def _kokoro_tts_text(self, text: str, language_name, voice_name: str, speed_factor, audio_format: str):
        try:
            # TTS voice
            kokoro_voice = self._get_kokoro_voice_manager().find_voice(language_name, voice_name)
                        
            # TTS
            source_audio_file = self.fm.get_split("Source.audio")                        
            aidub_audio_file = path_add_postfix(source_audio_file, f"_{voice_name}")        
            
            self._get_kokoro_tts().text_to_voice(text, aidub_audio_file, kokoro_voice, speed_factor, audio_format)

            self.fm.set_dubbing(f'{voice_name}.audio', aidub_audio_file)           

            # Mix
            mixed_audio_file = path_add_postfix(source_audio_file, f"_mixed_{voice_name}")            
            denoise_inst_path, _ = self._denoise(source_audio_file, 1)
            ffmpeg_mix_audio(aidub_audio_file, denoise_inst_path, mixed_audio_file, 0, 0, audio_format)
                                
            if self.has_video:
                source_video_file = self.fm.get_split("Source.video")
                aidub_video_file = path_add_postfix(source_video_file, f"_{voice_name}")
                
                ffmpeg_replace_audio(source_video_file, mixed_audio_file, aidub_video_file)
                
                self.fm.set_dubbing(f'{voice_name}.video', aidub_video_file)
                return aidub_video_file, mixed_audio_file
            else:
                return None, mixed_audio_file, 
        except Exception as e:
            logger.error(f"[gradio_gulliver.py] _kokoro_tts_text - Error : {e}")
            gr.Warning(f'{e}')
            return None, None    

    
    
    def _kokoro_tts_subtitle(self, 
                           subtitle_file, language_name, voice_name: str, speed_factor, audio_format: str):
        logger.debug(f"[gradio_gulliver.py] _kokoro_tts_subtitle - subtitle_file = {subtitle_file}, \
                    voice_name = {voice_name}, language_name = {language_name}, \
                    speed_factor = {speed_factor}, audio_format = {audio_format}")
        
        try:
            # TTS voice
            kokoro_voice = self._get_kokoro_voice_manager().find_voice(language_name, voice_name)
                        
            # TTS
            source_audio_file = self.fm.get_split("Source.audio")                        
            aidub_audio_file = path_add_postfix(source_audio_file, f"_{voice_name}")        
            
            self._get_kokoro_tts().srt_to_voice(subtitle_file, aidub_audio_file, kokoro_voice, speed_factor, audio_format)

            self.fm.set_dubbing(f'{voice_name}.audio', aidub_audio_file)           
        
            # Mix
            mixed_audio_file = path_add_postfix(source_audio_file, f"_mixed_{voice_name}")            
            denoise_inst_path, _ = self._denoise(source_audio_file, 1)
            ffmpeg_mix_audio(aidub_audio_file, denoise_inst_path, mixed_audio_file, 0, 0, audio_format)
                                
            if self.has_video:
                source_video_file = self.fm.get_split("Source.video")
                aidub_video_file = path_add_postfix(source_video_file, f"_{voice_name}")
                
                ffmpeg_replace_audio(source_video_file, mixed_audio_file, aidub_video_file)
                
                self.fm.set_dubbing(f'{voice_name}.video', aidub_video_file)
                return aidub_video_file, mixed_audio_file
            else:
                return None, mixed_audio_file
        except Exception as e:
            logger.error(f"[gradio_gulliver.py] _kokoro_tts_subtitle - Error : {e}")
            gr.Warning(f'{e}')
            return None, None         
