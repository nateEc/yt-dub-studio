import os
from pathlib import Path

import gradio as gr

import src.ui as ui
from app.abus_genuine import genuine_init
from app.abus_hf import AbusHuggingFace
from app.abus_path import path_gradio_folder, path_workspace_folder
from app.tab_youtube_pipeline import youtube_pipeline_css, youtube_pipeline_tab
from src.config import UserConfig


if __name__ == "__main__":
    genuine_init()
    AbusHuggingFace.initialize(app_name="voice")
    path_workspace_folder()
    path_gradio_folder()

    user_config_path = os.path.join(Path(__file__).resolve().parent, "app", "config-user.json5")
    user_config = UserConfig(user_config_path)

    with gr.Blocks(title="YouTube Pipeline", css=ui.css + "\n" + youtube_pipeline_css(), theme=ui.theme) as app:
        youtube_pipeline_tab(user_config)
        gr.Markdown("YouTube Pipeline | Voice-Pro", elem_classes=["no-translate"])
        app.load(None, None, None, js="() => document.getElementsByTagName('body')[0].classList.add('dark')")
        app.load(None, None, None, js=f"() => {{{ui.js}}}")

    inbrowser = os.environ.get("GRADIO_INBROWSER", "1").strip().lower() not in ("0", "false", "no")
    app.launch(share=False, server_name=None, server_port=7861, inbrowser=inbrowser)
