# -*- coding: utf-8 -*-
"""
UI callback functions for SoulX-Podcast WebUI.
"""

import re
import os
from datetime import datetime
from typing import List

import numpy as np
import gradio as gr
import soundfile as sf

from .constants import MAX_SPEAKERS, MAX_TEXT_INPUTS
from .i18n import (
    i18n,
    get_i18n_dict,
    get_speaker_display_label,
    get_language,
    set_language,
)
from .synthesis import dialogue_synthesis_function
from .file_manager import create_all_zip


# =============================================================================
# Speaker Management Callbacks
# =============================================================================

def update_speakers_visibility(num_speakers: int, remarks=None):
    """更新说话人列的可见性和标签"""
    remark_list = list(remarks) if remarks else []
    updates = []
    for i in range(MAX_SPEAKERS):
        visible = (i < num_speakers)
        remark_val = remark_list[i] if i < len(remark_list) else ""
        label = get_speaker_display_label(i + 1, remark_val)
        if visible:
            updates.append(gr.update(visible=True, label=label, value=False))
        else:
            updates.append(gr.update(visible=False, value=False))
    return updates


def add_speaker(current_num: int, *remarks):
    """添加一个说话人"""
    remark_list = list(remarks) if remarks else []
    new_num = min(current_num + 1, MAX_SPEAKERS)
    checkbox_updates = update_speakers_visibility(new_num, remark_list)
    column_updates = []
    for i in range(MAX_SPEAKERS):
        remark_val = remark_list[i] if i < len(remark_list) else ""
        column_updates.append(
            gr.update(
                visible=(i < new_num),
                label=get_speaker_display_label(i + 1, remark_val)
            )
        )
    return new_num, *checkbox_updates, *column_updates


def quick_add_speakers(current_num: int, add_count, *remarks):
    """快速添加指定数量的说话人"""
    remark_list = list(remarks) if remarks else []
    add_count = int(add_count) if add_count else 1
    add_count = max(1, min(add_count, MAX_SPEAKERS - current_num))
    new_num = min(current_num + add_count, MAX_SPEAKERS)
    checkbox_updates = update_speakers_visibility(new_num, remark_list)
    column_updates = []
    for i in range(MAX_SPEAKERS):
        remark_val = remark_list[i] if i < len(remark_list) else ""
        column_updates.append(
            gr.update(
                visible=(i < new_num),
                label=get_speaker_display_label(i + 1, remark_val)
            )
        )
    return new_num, *checkbox_updates, *column_updates


def batch_delete_speakers(current_num: int, *all_values):
    """批量删除选中的说话人，并重新排列剩余说话人及其数据"""
    # all_values格式: (checkbox1, audio1, text1, dialect1, remark1, checkbox2, ...)
    speaker_data = []
    for i in range(MAX_SPEAKERS):
        base = i * 5
        checkbox_val = all_values[base] if base < len(all_values) else False
        audio_val = all_values[base + 1] if base + 1 < len(all_values) else None
        text_val = all_values[base + 2] if base + 2 < len(all_values) else ""
        dialect_val = all_values[base + 3] if base + 3 < len(all_values) else ""
        remark_val = all_values[base + 4] if base + 4 < len(all_values) else ""
        speaker_data.append(
            dict(
                checkbox=checkbox_val,
                audio=audio_val,
                text=text_val,
                dialect=dialect_val,
                remark=remark_val,
            )
        )
    
    selected_indices = {
        i for i, spk in enumerate(speaker_data) if spk["checkbox"] and i < current_num
    }
    
    def _build_updates(target_num: int, kept: list):
        updates = []
        for i in range(MAX_SPEAKERS):
            if i < target_num and i < len(kept):
                spk = kept[i]
                label = get_speaker_display_label(i + 1, spk["remark"])
                updates.extend(
                    [
                        gr.update(visible=True, label=label, value=False),
                        gr.update(value=spk["audio"]),
                        gr.update(value=spk["text"]),
                        gr.update(value=spk["dialect"]),
                        gr.update(value=spk["remark"]),
                    ]
                )
            else:
                updates.extend(
                    [
                        gr.update(visible=False, value=False),
                        gr.update(value=None),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                    ]
                )
        tab_updates = [
            gr.update(
                visible=(i < target_num),
                label=get_speaker_display_label(
                    i + 1, kept[i]["remark"] if i < len(kept) else ""
                ),
            )
            for i in range(MAX_SPEAKERS)
        ]
        return updates, tab_updates
    
    if not selected_indices:
        gr.Warning("请至少选择一个说话人进行删除")
        kept_list = [speaker_data[i] for i in range(current_num)]
        updates, tab_updates = _build_updates(current_num, kept_list)
        return current_num, *updates, *tab_updates
    
    remaining_count = current_num - len(selected_indices)
    if remaining_count < 1:
        gr.Warning("至少需要保留1个说话人")
        kept_list = [speaker_data[i] for i in range(current_num)]
        updates, tab_updates = _build_updates(current_num, kept_list)
        return current_num, *updates, *tab_updates
    
    kept_indices = [i for i in range(current_num) if i not in selected_indices]
    kept_list = [speaker_data[i] for i in kept_indices]
    updates, tab_updates = _build_updates(remaining_count, kept_list)
    return remaining_count, *updates, *tab_updates


def select_all_checkboxes(current_num: int):
    """全选所有可见的复选框"""
    updates = []
    for i in range(MAX_SPEAKERS):
        if i < current_num:
            updates.append(gr.update(value=True))
        else:
            updates.append(gr.update())
    return updates


def select_none_checkboxes(current_num: int):
    """取消全选所有复选框"""
    updates = []
    for i in range(MAX_SPEAKERS):
        updates.append(gr.update(value=False))
    return updates


def update_single_speaker_label(remark: str, idx: int):
    """根据备注更新单个说话人的复选框与 Tab 标签"""
    label = get_speaker_display_label(idx, remark)
    return gr.update(label=label), gr.update(label=label)


# =============================================================================
# Text Input Management
# =============================================================================

def update_text_inputs_visibility(num_inputs):
    """更新文本输入框的可见性"""
    num = int(num_inputs) if num_inputs else 1
    num = max(1, min(num, MAX_TEXT_INPUTS))
    updates = []
    audio_updates = []
    download_updates = []
    for i in range(MAX_TEXT_INPUTS):
        is_visible = (i < num)
        updates.append(gr.update(
            visible=is_visible,
            label=f"{i18n('dialogue_text_input_label')} {i+1}"
        ))
        audio_updates.append(gr.update(visible=False))
        download_updates.append(gr.update(visible=False))
    return num, *updates, *audio_updates, *download_updates


# =============================================================================
# Synthesis Processing
# =============================================================================

def process_single_synthesis(
    target_text: str,
    num_speakers: int,
    seed: int,
    diff_spk_pause_ms: int,
    speaker_args: List,
    task_number: int,
    base_output_dir: str,
    timestamp: str,
):
    """
    处理单个合成任务
    task_number: 任务编号（从1开始）
    base_output_dir: 基础输出目录（时间戳文件夹）
    timestamp: 统一的时间戳
    """
    speaker_configs = []
    for i in range(0, min(num_speakers * 3, len(speaker_args)), 3):
        if i + 2 < len(speaker_args):
            audio = speaker_args[i] if speaker_args[i] is not None else None
            text = speaker_args[i+1] if speaker_args[i+1] is not None else ""
            dialect = speaker_args[i+2] if speaker_args[i+2] is not None else ""
            speaker_configs.append((text, audio, dialect))
    
    task_subdir = f"{task_number:03d}"
    output_dir = os.path.join(base_output_dir, task_subdir)
    os.makedirs(output_dir, exist_ok=True)
    
    audio_result, saved_files = dialogue_synthesis_function(
        target_text,
        speaker_configs,
        seed,
        int(diff_spk_pause_ms) if diff_spk_pause_ms is not None else 0,
        output_dir=output_dir,
        save_separated=True,
        timestamp=timestamp
    )
    
    return audio_result, saved_files, None, output_dir


def collect_and_synthesize_queue(
    num_text_inputs,
    num_speakers,
    seed,
    diff_spk_pause_ms,
    *all_text_and_speaker_args
):
    """
    处理队列中的所有任务
    all_text_and_speaker_args格式: (text1, ..., textN, audio1, text1, dialect1, ...)
    """
    global_lang = get_language()
    num_text = int(num_text_inputs) if num_text_inputs else 1
    num_speaker = int(num_speakers)
    
    text_inputs = list(all_text_and_speaker_args[:MAX_TEXT_INPUTS])
    speaker_args = list(all_text_and_speaker_args[MAX_TEXT_INPUTS:])
    
    valid_texts = []
    valid_indices = []
    for i, text in enumerate(text_inputs[:num_text]):
        if text and text.strip():
            valid_texts.append(text)
            valid_indices.append(i)
    
    if not valid_texts:
        empty_audio_updates = [gr.update(visible=False) for _ in range(MAX_TEXT_INPUTS)]
        empty_download_updates = [gr.update(visible=False) for _ in range(MAX_TEXT_INPUTS)]
        return (
            None,
            "所有输入框均为空，请至少填写一个文本输入",
            gr.update(visible=False),
            gr.update(interactive=True),
            *empty_audio_updates,
            *empty_download_updates,
        )
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_output_dir = os.path.join(os.getcwd(), "outputs", "separated_speakers", timestamp)
    os.makedirs(base_output_dir, exist_ok=True)
    
    progress_bar = gr.Progress(track_tqdm=True)
    all_info_messages = []
    task_audio_results = {}
    all_complete_audio_files = []
    all_generated_files = []
    
    for task_idx, (text_idx, target_text) in enumerate(zip(valid_indices, valid_texts)):
        progress_bar((task_idx, len(valid_texts)), desc=f"处理任务 {task_idx + 1}/{len(valid_texts)}")
        
        try:
            task_number = task_idx + 1
            audio_result, saved_files, zip_file_path, output_dir = process_single_synthesis(
                target_text, num_speaker, seed, diff_spk_pause_ms, speaker_args,
                task_number, base_output_dir, timestamp
            )
            
            task_audio_results[text_idx] = audio_result
            all_generated_files.extend(saved_files)
            
            complete_files = [f for f in saved_files if "complete_dialogue" in os.path.basename(f)]
            if complete_files:
                all_complete_audio_files.extend(complete_files)
            
            task_subdir_name = f"{task_number:03d}"
            info_message = f"═══════════════════════════════════\n"
            info_message += f"任务 {task_idx + 1}/{len(valid_texts)} (输入框 {text_idx + 1})\n"
            info_message += f"═══════════════════════════════════\n"
            info_message += f"{i18n('files_saved_to')}\n"
            info_message += f"基础文件夹: {os.path.abspath(base_output_dir)}\n"
            info_message += f"任务子文件夹: {task_subdir_name}/\n"
            info_message += f"完整路径: {os.path.abspath(output_dir)}\n\n"
            
            if saved_files:
                info_message += f"{i18n('files_generated_count').format(count=len(saved_files))}\n\n"
                
                complete_files = [f for f in saved_files if "complete_dialogue" in os.path.basename(f)]
                if complete_files:
                    info_message += f"📁 {i18n('complete_dialogue_audio')}:\n"
                    for f in complete_files:
                        info_message += f"  • {os.path.basename(f)}\n"
                    info_message += "\n"
                
                speaker_groups = {}
                for f in saved_files:
                    basename = os.path.basename(f)
                    if "speaker" in basename and "complete_dialogue" not in basename:
                        match = re.search(r'speaker(\d+)', basename)
                        if match:
                            spk_num = match.group(1)
                            if spk_num not in speaker_groups:
                                speaker_groups[spk_num] = []
                            speaker_groups[spk_num].append(basename)
                
                for spk_num in sorted(speaker_groups.keys(), key=int):
                    files = sorted(speaker_groups[spk_num])
                    complete_audio = [f for f in files if "_complete_" in f]
                    parts = [f for f in files if "_part" in f]
                    
                    info_message += f"🎤 {i18n('speaker_label').format(num=spk_num)}:\n"
                    if complete_audio:
                        for filename in complete_audio:
                            info_message += f"  • {filename} {i18n('complete_audio_label')}\n"
                    if parts:
                        for filename in sorted(parts):
                            info_message += f"  • {filename}\n"
                    info_message += "\n"
            else:
                info_message += f"{i18n('no_files_saved')}\n"
            
            all_info_messages.append(info_message)
            
        except Exception as e:
            error_msg = f"任务 {task_idx + 1} 处理失败: {str(e)}\n"
            all_info_messages.append(error_msg)
            import traceback
            traceback.print_exc()
    
    # 合并所有任务的完整对话音频
    merged_audio_path = None
    if all_complete_audio_files and len(all_complete_audio_files) > 0:
        try:
            merged_audio_path = os.path.join(base_output_dir, "all.wav")
            merged_audio_data = None
            sample_rate = 24000
            
            for audio_file in all_complete_audio_files:
                if os.path.exists(audio_file):
                    audio_data, sr = sf.read(audio_file)
                    if sample_rate != sr:
                        print(f"[WARNING] 采样率不一致: {audio_file} 为 {sr}Hz，期望 {sample_rate}Hz")
                    
                    if len(audio_data.shape) > 1:
                        audio_data = np.mean(audio_data, axis=1)
                    
                    if merged_audio_data is None:
                        merged_audio_data = audio_data
                    else:
                        pause_samples = int(0.5 * sample_rate)
                        silence = np.zeros(pause_samples)
                        merged_audio_data = np.concatenate([merged_audio_data, silence, audio_data])
            
            if merged_audio_data is not None:
                sf.write(merged_audio_path, merged_audio_data, sample_rate)
                print(f"[INFO] 已合并所有任务音频到: {merged_audio_path}")
                all_generated_files.append(merged_audio_path)
        except Exception as e:
            print(f"[ERROR] 合并音频文件时出错: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # 创建 all.zip
    all_zip_path = None
    if all_generated_files:
        all_zip_path = create_all_zip(base_output_dir, all_generated_files)
    
    # 构建最终信息
    final_info_message = f"📂 所有任务文件保存在统一的时间戳文件夹中:\n"
    final_info_message += f"   {os.path.abspath(base_output_dir)}\n"
    final_info_message += f"   每个任务的文件保存在对应的编号子文件夹中 (001/, 002/, 003/, ...)\n"
    final_info_message += f"   分段语音保存在各任务子文件夹的 separated/ 子文件夹中\n"
    if merged_audio_path and os.path.exists(merged_audio_path):
        final_info_message += f"   📁 合并音频文件: {os.path.basename(merged_audio_path)}\n"
    if all_zip_path and os.path.exists(all_zip_path):
        final_info_message += f"   📦 所有文件压缩包: {os.path.basename(all_zip_path)}\n"
    final_info_message += "\n"
    final_info_message += "═══════════════════════════════════\n\n"
    final_info_message += "\n\n".join(all_info_messages)
    final_info_message += f"\n\n✅ 已完成所有任务 ({len(valid_texts)}/{len(valid_texts)})"
    
    # 生成更新
    audio_preview_updates = []
    download_updates = []
    
    preview_audio_value = None
    if merged_audio_path and os.path.exists(merged_audio_path):
        try:
            audio_data, sample_rate = sf.read(merged_audio_path)
            preview_audio_value = (sample_rate, audio_data)
        except Exception as e:
            print(f"[WARNING] 读取 all.wav 文件失败: {str(e)}")
            if task_audio_results:
                preview_audio_value = list(task_audio_results.values())[-1]
    elif task_audio_results:
        preview_audio_value = list(task_audio_results.values())[-1]
    
    for i in range(MAX_TEXT_INPUTS):
        if i in task_audio_results:
            if global_lang == "zh":
                audio_label = f"任务 {i+1} 音频预览"
            else:
                audio_label = f"Task {i+1} Audio Preview"
            
            audio_preview_updates.append(gr.update(
                visible=True,
                value=task_audio_results[i],
                label=audio_label
            ))
            download_updates.append(gr.update(visible=False))
        else:
            audio_preview_updates.append(gr.update(visible=False))
            download_updates.append(gr.update(visible=False))
    
    download_file_update = None
    if all_zip_path and os.path.exists(all_zip_path):
        download_label = f"{i18n('download_all_files_label')} - all.zip"
        download_file_update = gr.update(visible=True, value=all_zip_path, label=download_label)
    else:
        download_file_update = gr.update(visible=False, value=None)
    
    return (
        preview_audio_value,
        final_info_message,
        download_file_update,
        gr.update(interactive=True),
        *audio_preview_updates,
        *download_updates,
    )


# =============================================================================
# Language Switch Callback
# =============================================================================

def change_component_language(lang, *remarks):
    """Change language for all components."""
    if isinstance(lang, str):
        set_language("zh" if lang == "中文" else "en")
    else:
        try:
            set_language(["zh", "en"][int(lang)])
        except Exception:
            set_language("zh")
    global_lang = get_language()
    i18n_dict = get_i18n_dict()
    
    checkbox_updates = []
    input_updates = []
    
    remark_list = list(remarks) if remarks else []
    for i in range(MAX_SPEAKERS):
        remark_val = remark_list[i] if i < len(remark_list) else ""
        checkbox_updates.append(gr.update(label=get_speaker_display_label(i + 1, remark_val)))
    
    for i in range(MAX_SPEAKERS):
        input_updates.extend([
            gr.update(label=i18n(f"spk{i+1}_prompt_audio_label") if f"spk{i+1}_prompt_audio_label" in i18n_dict else f"说话人 {i+1} 参考语音"),
            gr.update(
                label=i18n(f"spk{i+1}_prompt_text_label") if f"spk{i+1}_prompt_text_label" in i18n_dict else f"说话人 {i+1} 参考文本",
                placeholder=i18n(f"spk{i+1}_prompt_text_placeholder") if f"spk{i+1}_prompt_text_placeholder" in i18n_dict else f"说话人 {i+1} 参考文本",
            ),
            gr.update(
                label=i18n(f"spk{i+1}_dialect_prompt_text_label") if f"spk{i+1}_dialect_prompt_text_label" in i18n_dict else f"说话人 {i+1} 方言提示文本",
                placeholder=i18n(f"spk{i+1}_dialect_prompt_text_placeholder") if f"spk{i+1}_dialect_prompt_text_placeholder" in i18n_dict else "带前缀方言提示词思维链文本",
            ),
        ])
    
    updates = checkbox_updates + input_updates
    
    for i in range(MAX_TEXT_INPUTS):
        updates.append(gr.update(
            label=f"{i18n('dialogue_text_input_label')} {i+1}",
            placeholder=i18n("dialogue_text_input_placeholder"),
        ))
    
    for i in range(MAX_TEXT_INPUTS):
        if global_lang == "zh":
            updates.append(gr.update(label=f"任务 {i+1} 音频预览"))
            updates.append(gr.update(label=f"任务 {i+1} 下载"))
        else:
            updates.append(gr.update(label=f"Task {i+1} Audio Preview"))
            updates.append(gr.update(label=f"Task {i+1} Download"))
    
    updates.extend([
        gr.update(value=i18n("generate_btn_label")),
        gr.update(label=i18n("generated_audio_label")),
        gr.update(value=f"➕ {i18n('add_speaker_btn_label')}"),
        gr.update(label=i18n('quick_add_num_label')),
        gr.update(value=f"🚀 {i18n('quick_add_btn_label')}"),
        gr.update(value=f"☑️ {i18n('select_all_btn_label')}"),
        gr.update(value=f"☐ {i18n('select_none_btn_label')}"),
        gr.update(value=f"🗑️ {i18n('batch_delete_btn_label')}"),
        gr.update(
            label=i18n("separated_files_info_label"),
            placeholder=i18n("separated_files_info_placeholder"),
        ),
        gr.update(label=i18n("download_all_files_label")),
        gr.update(label=i18n("diff_spk_pause_label")),
    ])
    return updates

