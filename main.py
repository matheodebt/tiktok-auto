import anthropic
import requests
import os
import random
from datetime import datetime
import subprocess
import tempfile

ANTHROPIC_KEY    = os.environ["ANTHROPIC_KEY"]
ELEVEN_KEY       = os.environ["ELEVEN_KEY"]
ELEVEN_VOICE     = "pNInz6obpgDQGcFmaJgB"  # Adam
PEXELS_KEY       = os.environ["PEXELS_KEY"]
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

THEMES = [
    "un scandale financier réel méconnu du grand public",
    "une arnaque ou escroquerie réelle originale et peu connue",
    "un crime en col blanc réel et fascinant",
    "un krach boursier ou bulle financière historique surprenante",
    "un scandale ou effondrement dans l'univers crypto méconnu",
]

def generate_script():
    theme = random.choice(THEMES)
    prompt = f"""Tu es un narrateur TikTok viral. Tu racontes des histoires vraies choquantes qui clouent les gens à leur écran.

Écris un script de 80-100 mots sur {theme}.

RÈGLES ABSOLUES :
- Commence par UNE phrase de 5-8 mots maximum qui crée un choc immédiat.
- Phrases TRÈS courtes (5-10 mots max). Rythme haché. Comme un thriller.
- Vrais noms, dates, montants précis
- Au milieu : révélation qui retourne tout
- Fin : phrase qui fait froid dans le dos
- JAMAIS de titres, JAMAIS de hashtags
- Texte oral uniquement"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    script = message.content[0].text.strip()

    kw_prompt = f"Donne-moi 4 mots-clés en anglais séparés par des virgules pour trouver des vidéos de fond sur Pexels illustrant cette histoire. Réponds UNIQUEMENT avec les mots-clés : {script[:200]}"
    kw_msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=50,
        messages=[{"role": "user", "content": kw_prompt}]
    )
    keywords = [k.strip() for k in kw_msg.content[0].text.strip().split(",")][:4]

    return script, keywords

def generate_voice(script, output_path):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}"
    headers = {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"}
    body = {
        "text": script,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.25,
            "similarity_boost": 0.85,
            "style": 0.75,
            "use_speaker_boost": True
        }
    }
    r = requests.post(url, headers=headers, json=body)
    r.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(r.content)
    print("✓ Audio généré")

def get_audio_duration(audio_path):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True
    )
    return float(probe.stdout.strip())

def download_clip(kw, output_path):
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_KEY},
            params={"query": kw, "per_page": 10, "orientation": "portrait"},
            timeout=15
        )
        r.raise_for_status()
        videos = r.json().get("videos", [])
        if not videos:
            return False
        for video in random.sample(videos, min(4, len(videos))):
            files = video.get("video_files", [])
            sd_files = [f for f in files if f.get("quality") == "sd"]
            if sd_files:
                link = sd_files[0]["link"]
                data = requests.get(link, timeout=30).content
                if 500*1024 < len(data) < 15*1024*1024:
                    with open(output_path, "wb") as f:
                        f.write(data)
                    print(f"  ✓ Clip : {kw} ({len(data)//1024}KB)")
                    return True
    except Exception as e:
        print(f"  ⚠️ {kw}: {e}")
    return False

def assemble_video(audio_path, clip_paths, output_path):
    duration = get_audio_duration(audio_path)

    if not clip_paths:
        # Fond noir si pas de clips
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s=540x960:r=24:d={duration}",
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"ffmpeg black: {result.stderr[-200:]}")
        return

    tmp_dir = os.path.dirname(output_path)

    # Normalise chaque clip : scale + crop en 540x960
    normalized = []
    for i, clip in enumerate(clip_paths):
        out = os.path.join(tmp_dir, f"norm_{i}.mp4")
        cmd = [
            "ffmpeg", "-y", "-i", clip,
            "-vf", "scale=540:960:force_original_aspect_ratio=increase,crop=540:960,format=yuv420p",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-an", "-threads", "1", out
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            normalized.append(out)

    if not normalized:
        # Fallback fond noir
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s=540x960:r=24:d={duration}",
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", output_path
        ]
        subprocess.run(cmd, capture_output=True)
        return

    # Concat les clips en boucle jusqu'à couvrir la durée
    concat_file = os.path.join(tmp_dir, "concat.txt")
    clips_needed = int(duration / 5) + len(normalized) + 1
    with open(concat_file, "w") as f:
        for i in range(clips_needed):
            f.write(f"file '{normalized[i % len(normalized)]}'\n")

    concat_out = os.path.join(tmp_dir, "concat.mp4")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy", "-t", str(duration + 2), concat_out
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise Exception(f"concat failed: {r.stderr[-200:]}")

    # Merge video + audio
    cmd = [
        "ffmpeg", "-y",
        "-i", concat_out,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(duration),
        "-map", "0:v:0", "-map", "1:a:0",
        output_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise Exception(f"merge failed: {r.stderr[-200:]}")
    print("✓ Vidéo assemblée avec plusieurs clips")

def send_telegram(video_path, script):
    caption = f"🎬 {script[:900]}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    with open(video_path, "rb") as f:
        r = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption,
            "supports_streaming": True
        }, files={"video": f}, timeout=120)
    r.raise_for_status()
    print("✓ Vidéo envoyée sur Telegram")

def main():
    print(f"\n{'='*50}")
    print(f"TikTok Auto — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = os.path.join(tmp, "audio.mp3")
        out_path   = os.path.join(tmp, "final.mp4")

        print("1/4 Script...")
        script, keywords = generate_script()
        print(f"\nSCRIPT:\n{script}")
        print(f"\nMots-clés: {keywords}\n")

        print("2/4 Voix...")
        generate_voice(script, audio_path)

        print("3/4 Clips vidéo...")
        clip_paths = []
        for i, kw in enumerate(keywords):
            clip_path = os.path.join(tmp, f"clip_{i}.mp4")
            if download_clip(kw, clip_path):
                clip_paths.append(clip_path)

        print(f"  {len(clip_paths)} clips téléchargés")

        print("4/4 Assemblage...")
        assemble_video(audio_path, clip_paths, out_path)

        print("Envoi Telegram...")
        send_telegram(out_path, script)

    print("\n✅ Terminé !")

if __name__ == "__main__":
    main()
