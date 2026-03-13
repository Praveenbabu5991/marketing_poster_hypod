import os

def update_file():
    with open('backend/agents/tools/video_gen.py', 'r') as f:
        content = f.read()

    # 1. Add audio_script to signature
    content = content.replace(
"""    cta_text: str = "",
    negative_prompt: str = "",
    output_dir: str = "",
) -> dict:""",
"""    cta_text: str = "",
    negative_prompt: str = "",
    output_dir: str = "",
    audio_script: str = "",
) -> dict:"""
    )

    # 2. Add audio_script to docstring
    content = content.replace(
"""        negative_prompt: Elements to exclude.
        output_dir: Directory to save video.
    \"\"\"""",
"""        negative_prompt: Elements to exclude.
        output_dir: Directory to save video.
        audio_script: Voiceover text to generate and merge into the video.
    \"\"\""""
    )

    # 3. Replace the early return for <= 8s
    content = content.replace(
"""    if clamped_duration <= 8:
        return _generate_single_video(
            prompt, image_path, reference_image_paths, clamped_duration, aspect_ratio,
            logo_path, brand_name, brand_colors, company_overview, target_audience,
            products_services, cta_text, negative_prompt, output_dir
        )""",
"""    if clamped_duration <= 8:
        res = _generate_single_video(
            prompt, image_path, reference_image_paths, clamped_duration, aspect_ratio,
            logo_path, brand_name, brand_colors, company_overview, target_audience,
            products_services, cta_text, negative_prompt, output_dir
        )"""
    )

    # 4. Replace the return for stitched video at the end to set it to `res = ...`
    content = content.replace(
"""    return {
        "status": "success",
        "video_path": final_video,
        "filename": final_filename,
        "url": f"/generated/{final_filename}",
        "duration_seconds": clamped_duration,
        "aspect_ratio": aspect_ratio,
        "model": part1_res.get("model", ""),
        "mode": "stitched",
        "branded": part1_res.get("branded", False),
    }""",
"""    res = {
        "status": "success",
        "video_path": final_video,
        "filename": final_filename,
        "url": f"/generated/{final_filename}",
        "duration_seconds": clamped_duration,
        "aspect_ratio": aspect_ratio,
        "model": part1_res.get("model", ""),
        "mode": "stitched",
        "branded": part1_res.get("branded", False),
    }"""
    )

    # 5. We need to find the indentation block of the `res =` above, which is inside `generate_video`,
    # wait, the first replace changed `return` to `res =`. The second replace changed `return { ... }` to `res = { ... }`.
    # Now we need to append the audio processing block at the very end of the function, and then `return res`.
    
    # We will append the following logic right before the end of the file (or function):
    audio_logic = """
    if res.get("status") == "success" and audio_script:
        import uuid
        import subprocess
        from datetime import datetime
        
        _, _, GENERATED_DIR = _get_config()
        save_dir = output_dir or str(GENERATED_DIR)
        
        video_path = res["video_path"]
        audio_path = os.path.join(save_dir, f"audio_{uuid.uuid4().hex[:8]}.mp3")
        logger.info("[VIDEO] Generating audio for script...")
        
        try:
            # We assume edge-tts is in the venv
            edge_tts_bin = os.path.join(os.getcwd(), ".venv", "bin", "edge-tts")
            if not os.path.exists(edge_tts_bin):
                # Fallback to global if venv not found
                edge_tts_bin = "edge-tts"
                
            subprocess.run([
                edge_tts_bin, "--text", audio_script, "--write-media", audio_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if os.path.exists(audio_path):
                video_with_audio_path = os.path.join(save_dir, f"with_audio_{uuid.uuid4().hex[:8]}.mp4")
                
                # We use -stream_loop -1 on video to loop it if audio is longer, and -shortest to end with audio.
                subprocess.run([
                    "ffmpeg", "-stream_loop", "-1", "-i", video_path, "-i", audio_path, 
                    "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0",
                    "-shortest", video_with_audio_path, "-y"
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                if os.path.exists(video_with_audio_path):
                    try:
                        os.remove(video_path)
                    except:
                        pass
                    res["video_path"] = video_with_audio_path
                    res["filename"] = os.path.basename(video_with_audio_path)
                    res["url"] = f"/generated/{res['filename']}"
                
                try:
                    os.remove(audio_path)
                except:
                    pass
        except Exception as e:
            logger.error("[VIDEO] Failed to merge audio: %s", e)
            
    return res
"""
    content = content + audio_logic
    
    with open('backend/agents/tools/video_gen.py', 'w') as f:
        f.write(content)

update_file()
