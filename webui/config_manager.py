# -*- coding: utf-8 -*-
"""
Configuration import/export management for SoulX-Podcast WebUI.
"""

import os
import uuid
from datetime import datetime
from typing import List, Tuple

import gradio as gr

from .constants import CONFIG_DIR, MAX_SPEAKERS, MAX_TEXT_INPUTS
from .i18n import get_select_speaker_label
from .utils import coerce_audio_value_to_path, coerce_gradio_file_to_path
from .file_manager import (
    ensure_config_dir,
    list_config_files,
    read_json_file,
    write_json_file,
)


# =============================================================================
# Config Building
# =============================================================================

def build_current_config_dict(
    language_idx,
    seed,
    diff_spk_pause_ms,
    num_speakers,
    num_text_inputs,
    text_inputs: List[str],
    speaker_values: List,
) -> dict:
    """Build a configuration dictionary from current UI state."""
    # language_idx: 0=中文, 1=English
    language = "zh" if int(language_idx) == 0 else "en"
    num_speakers = int(num_speakers) if num_speakers else 1
    num_text_inputs = int(num_text_inputs) if num_text_inputs else 1

    # speaker_values 格式: [audio1, text1, dialect1, audio2, text2, dialect2, ...]
    speakers = []
    for i in range(MAX_SPEAKERS):
        base = i * 3
        audio_val = speaker_values[base] if base < len(speaker_values) else None
        text_val = speaker_values[base + 1] if base + 1 < len(speaker_values) else ""
        dialect_val = speaker_values[base + 2] if base + 2 < len(speaker_values) else ""
        speakers.append(
            {
                "prompt_audio": coerce_audio_value_to_path(audio_val),
                "prompt_text": text_val if text_val is not None else "",
                "dialect_prompt_text": dialect_val if dialect_val is not None else "",
            }
        )

    cfg = {
        "version": "1.0",
        "export_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "language": language,
        "num_speakers": num_speakers,
        "num_text_inputs": num_text_inputs,
        "seed": int(seed) if seed is not None else 1988,
        "diff_spk_pause_ms": int(diff_spk_pause_ms) if diff_spk_pause_ms is not None else 0,
        "speakers": speakers[:num_speakers],
        "text_inputs": [t if t is not None else "" for t in text_inputs[:num_text_inputs]],
    }
    return cfg


# =============================================================================
# Config Export
# =============================================================================

def export_current_config(
    language_idx,
    seed,
    diff_spk_pause_ms,
    num_speakers,
    num_text_inputs,
    *values,
) -> Tuple[str, str]:
    """
    Export current configuration to a JSON file.
    values: text_inputs(MAX_TEXT_INPUTS) + speaker_inputs(MAX_SPEAKERS*3)
    Returns: (file_path, status_message)
    """
    ensure_config_dir()
    text_inputs = list(values[:MAX_TEXT_INPUTS])
    speaker_values = list(values[MAX_TEXT_INPUTS:])

    cfg = build_current_config_dict(
        language_idx=language_idx,
        seed=seed,
        diff_spk_pause_ms=diff_spk_pause_ms,
        num_speakers=num_speakers,
        num_text_inputs=num_text_inputs,
        text_inputs=text_inputs,
        speaker_values=speaker_values,
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"soulx_podcast_config_{ts}.json"
    out_path = os.path.join(CONFIG_DIR, fname)
    # 极小概率同秒冲突，追加随机后缀
    if os.path.exists(out_path):
        out_path = os.path.join(CONFIG_DIR, f"soulx_podcast_config_{ts}_{uuid.uuid4().hex[:8]}.json")
    write_json_file(out_path, cfg)
    return out_path, f'✅ 已导出配置到: {out_path}\n（如果要在下拉菜单里看到新文件，请点击"刷新列表"）'


def refresh_config_dropdown(current_value):
    """Refresh the config dropdown with available files."""
    files = list_config_files()
    new_value = current_value if current_value in files else (files[0] if files else None)
    return gr.update(choices=files, value=new_value)


# =============================================================================
# Config Loading
# =============================================================================

def apply_loaded_config(cfg: dict) -> Tuple[list, str]:
    """
    将 cfg 应用到界面，返回一组 updates，顺序与 outputs 对齐。
    Returns: (updates_list, warning_text)
    """
    # 兼容旧字段/缺失字段
    num_speakers = int(cfg.get("num_speakers") or 1)
    num_speakers = max(1, min(num_speakers, MAX_SPEAKERS))

    num_text_inputs = int(cfg.get("num_text_inputs") or 1)
    num_text_inputs = max(1, min(num_text_inputs, MAX_TEXT_INPUTS))

    seed_val = int(cfg.get("seed") or 1988)
    diff_pause_val = int(cfg.get("diff_spk_pause_ms") or 0)

    speakers = cfg.get("speakers") or []
    text_inputs = cfg.get("text_inputs") or []

    # speakers_state, num_text_inputs_state, num_text_inputs_selector, seed_input, diff_spk_pause_input
    result = [
        num_speakers,
        num_text_inputs,
        gr.update(value=num_text_inputs),
        gr.update(value=seed_val),
        gr.update(value=diff_pause_val),
    ]

    # speaker checkboxes
    for i in range(MAX_SPEAKERS):
        if i < num_speakers:
            result.append(gr.update(visible=True, value=False, label=get_select_speaker_label(i + 1)))
        else:
            result.append(gr.update(visible=False, value=False))

    # speaker audio, text, dialect
    warnings = []
    audio_updates = []
    text_updates = []
    dialect_updates = []
    for i in range(MAX_SPEAKERS):
        if i < num_speakers:
            spk = speakers[i] if i < len(speakers) else {}
            audio_path = spk.get("prompt_audio")
            if isinstance(audio_path, str) and audio_path.strip():
                if not os.path.isabs(audio_path):
                    audio_path = os.path.join(CONFIG_DIR, audio_path)
                if not os.path.exists(audio_path):
                    warnings.append(f"说话人{i+1}参考语音不存在: {audio_path}")
                    audio_path = None
            else:
                audio_path = None
            audio_updates.append(gr.update(value=audio_path))
            text_updates.append(gr.update(value=spk.get("prompt_text", "") or ""))
            dialect_updates.append(gr.update(value=spk.get("dialect_prompt_text", "") or ""))
        else:
            audio_updates.append(gr.update(value=None))
            text_updates.append(gr.update(value=""))
            dialect_updates.append(gr.update(value=""))
    result.extend(audio_updates)
    result.extend(text_updates)
    result.extend(dialect_updates)

    # speaker columns
    for i in range(MAX_SPEAKERS):
        result.append(gr.update(visible=(i < num_speakers)))

    # dialogue text inputs
    for i in range(MAX_TEXT_INPUTS):
        if i < num_text_inputs:
            t = text_inputs[i] if i < len(text_inputs) else ""
            result.append(gr.update(visible=True, value=t))
        else:
            result.append(gr.update(visible=False, value=""))

    warn_text = ""
    if warnings:
        warn_text = "⚠️ 加载完成，但有部分资源缺失：\n- " + "\n- ".join(warnings)
    return result, warn_text


def _create_empty_updates():
    """Create empty updates for error cases."""
    empty_updates = []
    empty_updates.extend([
        1,  # speakers_state
        1,  # num_text_inputs_state
        gr.update(value=1),  # num_text_inputs_selector
        gr.update(value=1988),  # seed_input
        gr.update(value=0),  # diff_spk_pause_input
    ])
    for _ in range(MAX_SPEAKERS):
        empty_updates.append(gr.update(visible=False, value=False))  # checkboxes
    for _ in range(MAX_SPEAKERS):
        empty_updates.append(gr.update(value=None))  # audio
    for _ in range(MAX_SPEAKERS):
        empty_updates.append(gr.update(value=""))  # text
    for _ in range(MAX_SPEAKERS):
        empty_updates.append(gr.update(value=""))  # dialect
    for _ in range(MAX_SPEAKERS):
        empty_updates.append(gr.update(visible=False))  # columns
    for _ in range(MAX_TEXT_INPUTS):
        empty_updates.append(gr.update(visible=False, value=""))
    return empty_updates


def load_uploaded_and_apply(file_obj):
    """Load configuration from uploaded file and apply it."""
    path = coerce_gradio_file_to_path(file_obj)
    if not path or not os.path.exists(path):
        gr.Warning("请先选择一个 JSON 配置文件")
        empty_updates = _create_empty_updates()
        return (*empty_updates, "未选择文件，无法加载。")

    try:
        cfg = read_json_file(path)
    except Exception as e:
        gr.Warning(f"读取配置失败: {e}")
        empty_updates = _create_empty_updates()
        return (*empty_updates, f"读取配置失败: {e}")

    # 自动保存到 config/ 目录
    ensure_config_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.basename(path)
    safe_name = base_name if base_name.lower().endswith(".json") else f"{base_name}.json"
    save_name = f"uploaded_{ts}_{safe_name}"
    save_path = os.path.join(CONFIG_DIR, save_name)
    if os.path.exists(save_path):
        save_path = os.path.join(CONFIG_DIR, f"uploaded_{ts}_{uuid.uuid4().hex[:8]}_{safe_name}")
    try:
        write_json_file(save_path, cfg)
    except Exception as e:
        gr.Warning(f"保存配置到 config/ 失败: {e}")

    updates, warn_text = apply_loaded_config(cfg)
    status = f"✅ 已加载配置: {os.path.abspath(save_path)}"
    if warn_text:
        status += f"\n\n{warn_text}"
    status += '\n（若要在下拉菜单中看到新文件，请点击"刷新列表"）'
    return (*updates, status)


def load_selected_and_apply(selected_filename: str):
    """Load configuration from selected dropdown file and apply it."""
    if not selected_filename:
        gr.Warning("请先在下拉菜单选择一个配置文件")
        empty_updates = _create_empty_updates()
        return (*empty_updates, "未选择配置文件，无法加载。")
    
    path = os.path.join(CONFIG_DIR, selected_filename)
    if not os.path.exists(path):
        gr.Warning(f"配置文件不存在: {path}")
        empty_updates = _create_empty_updates()
        return (*empty_updates, f"配置文件不存在: {path}")
    
    try:
        cfg = read_json_file(path)
    except Exception as e:
        gr.Warning(f"读取配置失败: {e}")
        empty_updates = _create_empty_updates()
        return (*empty_updates, f"读取配置失败: {e}")

    updates, warn_text = apply_loaded_config(cfg)
    status = f"✅ 已加载配置: {os.path.abspath(path)}"
    if warn_text:
        status += f"\n\n{warn_text}"
    return (*updates, status)

