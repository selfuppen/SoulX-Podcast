# -*- coding: utf-8 -*-
"""
Main interface rendering for SoulX-Podcast WebUI.
"""

import os
import gradio as gr

from .constants import MAX_SPEAKERS, MAX_TEXT_INPUTS
from .i18n import i18n, get_i18n_dict
from .file_manager import list_config_files
from .components import create_speaker_group
from .callbacks import (
    add_speaker,
    quick_add_speakers,
    batch_delete_speakers,
    select_all_checkboxes,
    select_none_checkboxes,
    update_text_inputs_visibility,
    collect_and_synthesize_queue,
    change_component_language,
)
from .config_manager import (
    export_current_config,
    refresh_config_dropdown,
    load_uploaded_and_apply,
    load_selected_and_apply,
)

# Custom CSS for better UI
CSS = """
.container { max_width: 1200px; margin: auto; padding-top: 20px; }
.header-img { margin: auto; width: 300px; display: block; margin-bottom: 20px; }
.generate-btn { font-size: 1.2em; font-weight: bold; min-height: 80px; }
.section-header { margin-top: 20px; margin-bottom: 10px; font-size: 1.2em; font-weight: bold; border-bottom: 1px solid #eee; padding-bottom: 5px; }
footer { visibility: hidden; }
"""

def render_interface() -> gr.Blocks:
    """Render the main Gradio interface."""
    _i18n_key2lang_dict = get_i18n_dict()
    
    with gr.Blocks(title="SoulX-Podcast", theme=gr.themes.Soft(primary_hue="indigo", secondary_hue="slate"), css=CSS) as page:

        # Header with Logo
        with gr.Row(elem_classes=["container"]):
            gr.Image(
                os.path.join("assets", "SoulX-Podcast-log.jpg"),
                show_label=False,
                container=False,
                elem_classes="header-img",
                interactive=False,
                show_download_button=False
            )

        with gr.Row():
            # ================= Left Column: Inputs =================
            with gr.Column(scale=7):
                
                # --- Speakers Section ---
                gr.Markdown("### 👥 说话人设置 / Speakers", elem_classes=["section-header"])
                
                # 说话人状态管理
                speakers_state = gr.State(value=1)
                
                # 创建所有说话人组件
                speaker_checkbox_list = []
                speaker_audio_list = []
                speaker_text_list = []
                speaker_dialect_list = []
                speaker_columns = []
                
                # 说话人列表容器
                with gr.Row() as speakers_row:
                    for i in range(MAX_SPEAKERS):
                        with gr.Column(scale=1, visible=(i < 1)) as col:
                            group, checkbox, audio, text, dialect = create_speaker_group(i + 1)
                            speaker_checkbox_list.append(checkbox)
                            speaker_audio_list.append(audio)
                            speaker_text_list.append(text)
                            speaker_dialect_list.append(dialect)
                            speaker_columns.append(col)
                
                # 添加/删除说话人按钮
                with gr.Row():
                    add_speaker_btn = gr.Button(f"➕ {i18n('add_speaker_btn_label')}", variant="secondary", scale=1)
                    with gr.Group():
                        quick_add_num = gr.Number(
                            label=i18n("quick_add_num_label"),
                            value=1,
                            minimum=1,
                            maximum=MAX_SPEAKERS,
                            step=1,
                            precision=0,
                            scale=1,
                        )
                        quick_add_btn = gr.Button(f"🚀 {i18n('quick_add_btn_label')}", variant="primary", scale=1)
                    select_all_btn = gr.Button(f"☑️ {i18n('select_all_btn_label')}", variant="secondary", scale=0)
                    select_none_btn = gr.Button(f"☐ {i18n('select_none_btn_label')}", variant="secondary", scale=0)
                    batch_delete_btn = gr.Button(f"🗑️ {i18n('batch_delete_btn_label')}", variant="stop", scale=1)

                # --- Dialogue Section ---
                gr.Markdown("### 📝 对话内容 / Dialogue", elem_classes=["section-header"])
                
                # 多输入框配置
                num_text_inputs_state = gr.State(value=1)
                
                with gr.Row():
                    num_text_inputs_selector = gr.Number(
                        label="输入框数量",
                        value=1,
                        minimum=1,
                        maximum=MAX_TEXT_INPUTS,
                        step=1,
                        precision=0,
                        interactive=True,
                        scale=1,
                    )
                
                # 创建多个文本输入框及其对应的预览和下载组件
                dialogue_text_inputs_list = []
                dialogue_audio_preview_list = []
                dialogue_download_list = []
                dialogue_text_inputs_container = gr.Column()
                with dialogue_text_inputs_container:
                    for i in range(MAX_TEXT_INPUTS):
                        dialogue_text_input = gr.Textbox(
                            label=f"{i18n('dialogue_text_input_label')} {i+1}",
                            placeholder=i18n("dialogue_text_input_placeholder"),
                            lines=12,
                            visible=(i < 1),
                        )
                        dialogue_text_inputs_list.append(dialogue_text_input)
                        
                        with gr.Row():
                            task_audio_preview = gr.Audio(
                                label=f"任务 {i+1} 音频预览 / Task {i+1} Audio Preview",
                                interactive=False,
                                visible=False,
                            )
                            task_download = gr.File(
                                label=f"任务 {i+1} 下载 / Task {i+1} Download",
                                visible=False,
                            )
                        dialogue_audio_preview_list.append(task_audio_preview)
                        dialogue_download_list.append(task_download)

            # ================= Right Column: Settings & Output =================
            with gr.Column(scale=5):
                
                # --- Global Settings ---
                gr.Markdown("### ⚙️ 全局设置 / Settings", elem_classes=["section-header"])
                
                with gr.Group():
                    lang_choice = gr.Radio(
                        choices=["中文", "English"],
                        value="中文",
                        label="Display Language/显示语言",
                        type="index",
                        interactive=True,
                    )
                    with gr.Row():
                        seed_input = gr.Number(
                            label="Seed (种子)",
                            value=1988,
                            step=1,
                            interactive=True,
                            scale=1,
                        )
                        diff_spk_pause_input = gr.Number(
                            label=i18n("diff_spk_pause_label") if "diff_spk_pause_label" in _i18n_key2lang_dict else "不同说话者间停顿(ms)",
                            value=0,
                            minimum=0,
                            step=50,
                            interactive=True,
                            scale=1,
                        )
                
                # --- Action Area ---
                gr.Markdown("### 🚀 生成 / Generate", elem_classes=["section-header"])
                
                generate_btn = gr.Button(
                    value=i18n("generate_btn_label"),
                    variant="primary",
                    elem_classes=["generate-btn"],
                )
                
                # --- Output Area ---
                gr.Markdown("### 📤 输出结果 / Output", elem_classes=["section-header"])
                
                # Long output audio
                generate_audio = gr.Audio(
                    label=i18n("generated_audio_label"),
                    interactive=False,
                )
                
                with gr.Accordion("详细文件信息 / File Info", open=True):
                    # 分离音频文件信息
                    separated_files_info = gr.Textbox(
                        label=i18n("separated_files_info_label"),
                        placeholder=i18n("separated_files_info_placeholder"),
                        interactive=False,
                        lines=6,
                        visible=True,
                        show_label=False,
                    )
                    
                    # 下载文件组件
                    download_file = gr.File(
                        label=i18n("download_all_files_label"),
                        visible=False,
                    )

                # --- Config Management ---
                with gr.Accordion("🛠️ 配置管理 / Config Management", open=False):
                    with gr.Row():
                        export_config_btn = gr.Button("导出当前配置", variant="secondary")
                        export_config_file = gr.File(label="导出的配置文件", interactive=False)
                    export_config_status = gr.Textbox(label="导出提示", interactive=False, lines=2)

                    gr.Markdown("**方式 1：上传 JSON 文件导入**")
                    with gr.Row():
                        import_config_uploader = gr.File(label="导入配置", file_types=[".json"])
                        load_uploaded_config_btn = gr.Button("加载配置", variant="primary")
                    load_uploaded_status = gr.Textbox(label="导入/加载提示", interactive=False, lines=3)

                    gr.Markdown("**方式 2：从 `config/` 目录选择导入**")
                    with gr.Row():
                        config_dropdown = gr.Dropdown(
                            label="config 目录中的配置文件",
                            choices=list_config_files(),
                            value=None,
                            interactive=True,
                            allow_custom_value=False,
                        )
                        refresh_config_list_btn = gr.Button("刷新列表", variant="secondary")
                        load_selected_config_btn = gr.Button("加载选中配置", variant="primary")
                    load_selected_status = gr.Textbox(label="加载提示", interactive=False, lines=3)

        # ================= Event Handlers =================
        
        # Speaker Management Events
        add_speaker_btn.click(
            fn=add_speaker,
            inputs=[speakers_state],
            outputs=[speakers_state] + speaker_checkbox_list + speaker_columns
        )
        
        quick_add_btn.click(
            fn=quick_add_speakers,
            inputs=[speakers_state, quick_add_num],
            outputs=[speakers_state] + speaker_checkbox_list + speaker_columns
        )
        
        select_all_btn.click(
            fn=select_all_checkboxes,
            inputs=[speakers_state],
            outputs=speaker_checkbox_list
        )
        
        select_none_btn.click(
            fn=select_none_checkboxes,
            inputs=[speakers_state],
            outputs=speaker_checkbox_list
        )
        
        # 准备批量删除的输入输出
        all_speaker_inputs_for_delete = []
        for i in range(MAX_SPEAKERS):
            all_speaker_inputs_for_delete.extend([
                speaker_checkbox_list[i],
                speaker_audio_list[i],
                speaker_text_list[i],
                speaker_dialect_list[i]
            ])
        
        all_speaker_outputs_for_delete = []
        for i in range(MAX_SPEAKERS):
            all_speaker_outputs_for_delete.extend([
                speaker_checkbox_list[i],
                speaker_audio_list[i],
                speaker_text_list[i],
                speaker_dialect_list[i]
            ])
        
        batch_delete_btn.click(
            fn=batch_delete_speakers,
            inputs=[speakers_state] + all_speaker_inputs_for_delete,
            outputs=[speakers_state] + all_speaker_outputs_for_delete + speaker_columns
        )

        # 更新输入框数量
        num_text_inputs_selector.change(
            fn=update_text_inputs_visibility,
            inputs=[num_text_inputs_selector],
            outputs=[num_text_inputs_state] + dialogue_text_inputs_list + dialogue_audio_preview_list + dialogue_download_list
        )

        # Config Events
        all_speaker_inputs_for_config = []
        for i in range(MAX_SPEAKERS):
            all_speaker_inputs_for_config.extend([
                speaker_audio_list[i],
                speaker_text_list[i],
                speaker_dialect_list[i],
            ])

        export_config_btn.click(
            fn=export_current_config,
            inputs=[
                lang_choice,
                seed_input,
                diff_spk_pause_input,
                speakers_state,
                num_text_inputs_state,
                *dialogue_text_inputs_list,
                *all_speaker_inputs_for_config,
            ],
            outputs=[export_config_file, export_config_status],
        )

        refresh_config_list_btn.click(
            fn=refresh_config_dropdown,
            inputs=[config_dropdown],
            outputs=[config_dropdown],
        )

        load_uploaded_config_btn.click(
            fn=load_uploaded_and_apply,
            inputs=[import_config_uploader],
            outputs=[
                speakers_state,
                num_text_inputs_state,
                num_text_inputs_selector,
                seed_input,
                diff_spk_pause_input,
                *speaker_checkbox_list,
                *speaker_audio_list,
                *speaker_text_list,
                *speaker_dialect_list,
                *speaker_columns,
                *dialogue_text_inputs_list,
                load_uploaded_status,
            ],
        )

        load_selected_config_btn.click(
            fn=load_selected_and_apply,
            inputs=[config_dropdown],
            outputs=[
                speakers_state,
                num_text_inputs_state,
                num_text_inputs_selector,
                seed_input,
                diff_spk_pause_input,
                *speaker_checkbox_list,
                *speaker_audio_list,
                *speaker_text_list,
                *speaker_dialect_list,
                *speaker_columns,
                *dialogue_text_inputs_list,
                load_selected_status,
            ],
        )

        # Generate Events
        all_speaker_inputs = []
        for i in range(MAX_SPEAKERS):
            all_speaker_inputs.extend([
                speaker_audio_list[i],
                speaker_text_list[i],
                speaker_dialect_list[i]
            ])
        
        generate_btn.click(
            fn=collect_and_synthesize_queue,
            inputs=(
                [num_text_inputs_state] +
                [speakers_state, seed_input, diff_spk_pause_input] +
                dialogue_text_inputs_list +
                all_speaker_inputs
            ),
            outputs=[
                generate_audio,
                separated_files_info,
                download_file,
                generate_btn,
                *dialogue_audio_preview_list,
                *dialogue_download_list,
            ],
        )
        
        # Language Switch Event
        lang_choice.change(
            fn=change_component_language,
            inputs=[lang_choice],
            outputs=(
                speaker_checkbox_list +
                all_speaker_inputs +
                dialogue_text_inputs_list +
                dialogue_audio_preview_list +
                dialogue_download_list +
                [
                    generate_btn,
                    generate_audio,
                    add_speaker_btn,
                    quick_add_num,
                    quick_add_btn,
                    select_all_btn,
                    select_none_btn,
                    batch_delete_btn,
                    separated_files_info,
                    download_file,
                    diff_spk_pause_input,
                ]
            ),
        )
    
    return page
