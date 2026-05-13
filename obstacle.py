# -*- coding: utf-8 -*-
"""

@author: csongor666
"""

import time
import math
import json
import os
import sys
import queue
import random
from dataclasses import dataclass
import numpy as np
import pygame
import sounddevice as sd
from scipy.signal import butter, lfilter

# =============================================================================
# SZÍN PARAMÉTEREK
# =============================================================================

# ---Elsődleges Színek ---

MY_RED           = pygame.Color(223,   0,  36)      # Hivatalos  piros (brand szín) [13]
MY_DARK_RED      = pygame.Color(180,   0,   0)      # Sötétebb  piros (árnyék, hover) - Eredeti érték
MY_WHITE         = pygame.Color(255, 255, 255)      # Fehér [13]
MY_BLACK         = pygame.Color(  0,   0,   0)      # Fekete [2]

# --- Szürke Skála (eredeti értékek megtartva) ---
MY_DARK_GRAY     = pygame.Color( 50,  50,  50)      # Sötét szürke (háttér, panelek)
MY_MID_GRAY      = pygame.Color(120, 120, 120)      # Közepes szürke (másodlagos elemek)
MY_LIGHT_GRAY    = pygame.Color(200, 200, 200)      # Világos szürke (keretek, elválasztók)
MY_PANEL_BG      = pygame.Color( 40,  40,  40)      # Panel háttér

# --- Másodlagos / Akcentus Színek (eredeti értékek megtartva) ---
MY_BLUE          = pygame.Color(  0, 120, 215)      # Kék (interaktív elemek, linkek)
MY_LIGHT_BLUE    = pygame.Color(  0, 170, 255)      # Világos kék (highlight)
MY_GREEN         = pygame.Color(  0, 168,  90)      # Zöld (siker, pozitív visszajelzés)
MY_YELLOW        = pygame.Color(255, 200,   0)      # Sárga / Amber (figyelmeztetés, kiemelés)
MY_ORANGE        = pygame.Color(255, 130,   0)      # Narancs (warning)


# --- UI Szerepkör Szerinti Színek ---
COLOR_BACKGROUND        = MY_DARK_GRAY       # Általános háttér
COLOR_PANEL_BG          = MY_PANEL_BG        # Panel / overlay háttér
COLOR_PANEL_BORDER      = MY_LIGHT_GRAY      # Panel keret
COLOR_TEXT_PRIMARY      = MY_WHITE           # Elsődleges szöveg
COLOR_TEXT_SECONDARY    = MY_LIGHT_GRAY      # Másodlagos szöveg
COLOR_TEXT_HIGHLIGHT    = MY_YELLOW          # Kiemelt szöveg (pl. ranglista)
COLOR_TEXT_DANGER       = MY_RED             # Hibaüzenetek, Game Over

# --- Játék Elem Színek ---
COLOR_OBSTACLE          = MY_RED             # Akadályok
COLOR_OBSTACLE_SHADOW   = MY_DARK_RED        # Akadály árnyéka
COLOR_PLAYER            = MY_YELLOW          # Játékos karakter
COLOR_PLAYER_EYE        = MY_BLACK           # Játékos szeme
COLOR_PLAYER_MOUTH      = MY_BLACK           # Játékos szája

# --- UI Vezérlő Elem Színek ---
COLOR_SLIDER_BG         = MY_BLACK           # Csúszka háttér
COLOR_SLIDER_KNOB       = MY_BLUE            # Csúszka gomb
COLOR_BAR_RAW_FILL      = MY_YELLOW          # Raw input sáv kitöltés
COLOR_BAR_FINAL_FILL    = MY_GREEN           # Final volume sáv kitöltés
COLOR_BAR_THRESHOLD     = MY_RED             # Küszöbszint jelző vonal

# --- Waveform Szín (from → to, volume alapján interpolálva) ---
COLOR_WAVEFORM_LOW      = MY_BLUE            # Alacsony hangerő szín
COLOR_WAVEFORM_HIGH     = MY_YELLOW          # Magas hangerő szín

# --- Particle Rendszer Színek ---
COLOR_TRAIL_PARTICLES   = [(169, 169, 169), (128, 128, 128)]   # Csóva részecskék
COLOR_SPARK_PARTICLES   = [(255, 200, 0), (255, 130, 0)]        # Ütközési szikrák ( sárga/narancs)

# --- Ranglista Helyezés Színek ---
COLOR_RANK_TOP3         = MY_YELLOW          # Top 3 arany kiemelés
COLOR_RANK_DEFAULT      = MY_WHITE           # Többi helyezés

# =============================================================================
# KONSTANSOK
# =============================================================================

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
FPS = 60
MAX_VOLUME_HEIGHT = 400
INITIAL_PLAYER_LIVES = 3

# Nehézségi paraméterek
OBSTACLE_START_DISTANCE = 1000
OBSTACLE_MIN_GAP, MIN_GAP_SIZE = 200, 100
GAP_REDUCTION_RATE, WIDTH_INCREASE_RATE = 0.95, 1.05
OBSTACLE_MIN_WIDTH, OBSTACLE_MAX_WIDTH = 30, 60
OBSTACLE_BASE_FREQUENCY, OBSTACLE_FREQUENCY_VARIANCE = 500, 100
DIFFICULTY_SCALE_DISTANCE = 1000

# Sebesség és irányítás
BASE_GAME_SPEED, MAX_GAME_SPEED = 4, 12
SPEED_INCREASE_RATE, PLAYER_SMOOTHNESS = 0.0008, 0.15

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
print(pygame.mixer.get_init())

# =============================================================================
# HANG GENERÁLÁS ÉS KEZELÉS
# =============================================================================

def generate_sound(frequency=440, duration=0.1, sample_rate=44100):
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, False)
    wave = np.sin(frequency * t * 2 * np.pi) * np.blackman(n_samples)
    wave = (wave * 32767).astype(np.int16)
    stereo_wave = np.repeat(wave.reshape(n_samples, 1), 2, axis=1)
    return pygame.sndarray.make_sound(stereo_wave)


class SoundManager:
    def __init__(self):
        self.collision_sound = generate_sound(frequency=120, duration=0.3)
        self.pass_obstacle_sound = generate_sound(frequency=880, duration=0.1)
        self.drum_beat = generate_sound(frequency=80, duration=0.15)
        self.pass_obstacle_sound.set_volume(0.5)
        self.drum_beat.set_volume(0.6)


class AdaptiveMusic:
    def __init__(self, sound_manager):
        self.sound_manager = sound_manager
        self.last_beat_time = 0
        self.beat_interval = 0.5

    def update(self, game_speed, obstacles, camera_offset):
        if any(0 < obs.top_rect.x - camera_offset < SCREEN_WIDTH for obs in obstacles):
            current_time = time.time()
            dynamic_interval = self.beat_interval * (MAX_GAME_SPEED / (game_speed * 1.5))
            if current_time - self.last_beat_time > dynamic_interval:
                self.sound_manager.drum_beat.play()
                self.last_beat_time = current_time

# =============================================================================
# UI ÉS BEÁLLÍTÁSOK
# =============================================================================

class SettingsPanel:
    def __init__(self, x, y, w, h, font):
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font
        self.sliders = {
            "Sensitivity": {
                "rect": pygame.Rect(x + 50, y + 60, 200, 20),
                "value": 0.5
            },
            "Threshold": {
                "rect": pygame.Rect(x + 50, y + 130, 200, 20),
                "value": 0.1
            }
        }
        self.dragging = None

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, s in self.sliders.items():
                if s["rect"].collidepoint(event.pos):
                    self.dragging = name
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = None
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.sliders[self.dragging]["value"] = np.clip(
                (event.pos[0] - self.sliders[self.dragging]["rect"].x)
                / self.sliders[self.dragging]["rect"].width,
                0, 1
            )

    def draw(self, screen, raw_rms, final_volume):
        # Panel alap és keret
        pygame.draw.rect(screen, COLOR_PANEL_BG, self.rect, border_radius=10)
        pygame.draw.rect(screen, COLOR_PANEL_BORDER, self.rect, 2, border_radius=10)

        # Cím
        title = self.font.render("Audio Settings", True, COLOR_TEXT_PRIMARY)
        screen.blit(title, (self.rect.centerx - title.get_width() // 2, self.rect.y + 15))

        # Csúszkák
        for name, s in self.sliders.items():
            label = self.font.render(f"{name}: {s['value']:.2f}", True, COLOR_TEXT_PRIMARY)
            screen.blit(label, (s["rect"].x, s["rect"].y - 25))
            pygame.draw.rect(screen, COLOR_SLIDER_BG, s["rect"])
            knob_x = s["rect"].x + int(s["value"] * s["rect"].width)
            pygame.draw.rect(screen, COLOR_SLIDER_KNOB, (knob_x - 5, s["rect"].y - 5, 10, 30))

        # Raw Input sáv
        raw_label = self.font.render("Raw Input", True, COLOR_TEXT_PRIMARY)
        screen.blit(raw_label, (self.rect.x + 50, self.rect.y + 175))
        raw_bar = pygame.Rect(self.rect.x + 50, self.rect.y + 195, 200, 30)
        pygame.draw.rect(screen, COLOR_SLIDER_BG, raw_bar)
        raw_fill = min(raw_rms * 10, 1.0)
        pygame.draw.rect(screen, COLOR_BAR_RAW_FILL,
                         (raw_bar.x, raw_bar.y, raw_fill * raw_bar.width, raw_bar.height))
        threshold_pos = self.get_value("Threshold") * raw_bar.width
        pygame.draw.line(screen, COLOR_BAR_THRESHOLD,
                         (raw_bar.x + threshold_pos, raw_bar.top),
                         (raw_bar.x + threshold_pos, raw_bar.bottom), 2)

        # Final Volume sáv
        final_label = self.font.render("Final Volume", True, COLOR_TEXT_PRIMARY)
        screen.blit(final_label, (self.rect.x + 50, self.rect.y + 240))
        final_bar = pygame.Rect(self.rect.x + 50, self.rect.y + 260, 200, 30)
        pygame.draw.rect(screen, COLOR_SLIDER_BG, final_bar)
        pygame.draw.rect(screen, COLOR_BAR_FINAL_FILL,
                         (final_bar.x, final_bar.y,
                          int(np.clip(final_volume, 0, 1) * final_bar.width),
                          final_bar.height))

    def get_value(self, name):
        return self.sliders[name]["value"]

# =============================================================================
# AUDIO PROCESSZOR
# =============================================================================

class AudioProcessor:
    def __init__(self, settings_panel, sample_rate=44100, block_size=4096):
        self.settings_panel = settings_panel
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.audio_queue = queue.Queue()
        self.stream = None
        self.volume = 0
        self.raw_rms = 0
        self.waveform_data = np.zeros(block_size)
        try:
            self.b, self.a = butter(4, [100, 2000], btype='band', fs=sample_rate)
        except Exception as e:
            print(f"Filter error: {e}")
            self.b, self.a = (None, None)

    def audio_callback(self, indata, frames, time, status):
        if status:
            print(status, flush=True)
        self.audio_queue.put(indata.copy())

    def start(self):
        if self.stream:
            return
        try:
            self.stream = sd.InputStream(
                callback=self.audio_callback,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size
            )
            self.stream.start()
            print(f"Stream elindult: {self.stream.active}")
            print(f"Eszköz: {sd.query_devices(kind='input')['name']}")
        except Exception as e:
            print(f"Audio stream error: {e}")
            self.stream = None

    def process_audio(self):
        if not self.stream:
            return
        try:
            while not self.audio_queue.empty():
                data = self.audio_queue.get()[:, 0]
                filtered = lfilter(self.b, self.a, data) if self.b is not None else data
                self.waveform_data = filtered
                self.raw_rms = np.sqrt(np.mean(filtered ** 2))

                threshold = self.settings_panel.get_value("Threshold") * 0.05
                sensitivity = 20 + self.settings_panel.get_value("Sensitivity") * 100

                if self.raw_rms < threshold:
                    self.volume = 0
                else:
                    self.volume = np.clip((self.raw_rms - threshold) * sensitivity, 0, 1)
        except Exception:
            pass

    def get_volume(self):
        return self.volume

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

# =============================================================================
# JÁTÉK KOMPONENSEK
# =============================================================================

class ParallaxBackground:
    def __init__(self):
        self.threshold = 500
        self.index = -1
        self.biomes = self._create_biomes()
        self.layers = []
        self.sky_color = self.biomes[list(self.biomes.keys())[0]]["sky_color"]

    def _create_biomes(self):
        return {
            "forest": {
                "sky_color": (135, 206, 235),
                "layers": [
                    {"s": 0.2, "c": (34, 139, 34),  "h": 300, "y": 300},
                    {"s": 0.5, "c": (0, 100, 0),     "h": 200, "y": 400},
                    {"s": 1.0, "c": (85, 107, 47),   "h": 100, "y": 500},
                ]
            },
            "desert": {
                "sky_color": (240, 230, 140),
                "layers": [
                    {"s": 0.2, "c": (210, 180, 140), "h": 250, "y": 350},
                    {"s": 0.5, "c": (188, 143, 143), "h": 150, "y": 450},
                    {"s": 1.0, "c": (205, 133, 63),  "h": 100, "y": 500},
                ]
            },
            "night": {
                "sky_color": (25, 25, 112),
                "layers": [
                    {"s": 0.1, "c": (75, 0, 130, 100), "h": 400, "y": 200},
                    {"s": 0.4, "c": (47, 79, 79),       "h": 250, "y": 350},
                    {"s": 1.0, "c": (0, 0, 0),           "h": 100, "y": 500},
                ]
            }
        }

    def update(self, dist, screen):
        biome_idx = int(dist // self.threshold) % len(self.biomes)
        if biome_idx != self.index:
            self.index = biome_idx
            name = list(self.biomes.keys())[biome_idx]
            self.layers = self.biomes[name]["layers"]
            self.sky_color = self.biomes[name]["sky_color"]
        screen.fill(self.sky_color)

    def draw(self, screen, cam_off):
        for l in self.layers:
            x = -(cam_off * l["s"] % SCREEN_WIDTH)
            r = pygame.Rect(0, l["y"], SCREEN_WIDTH, l["h"])
            pygame.draw.rect(screen, l["c"], r.move(x, 0))
            pygame.draw.rect(screen, l["c"], r.move(x + SCREEN_WIDTH, 0))


class Particle:
    def __init__(self, x, y, vx, vy, color, size, lifetime):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.color = color
        self.size = size
        self.lifetime = lifetime
        self.init_life = lifetime

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.lifetime -= 1
        self.current_color = (*self.color, max(0, int(255 * (self.lifetime / self.init_life))))

    def draw(self, surf, cam_off):
        if self.lifetime > 0:
            s = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, self.current_color, (self.size, self.size), self.size)
            surf.blit(s, (int(self.x - cam_off - self.size), int(self.y - self.size)))


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit_trail(self, pos):
        if random.random() < 0.8:
            self.particles.append(Particle(
                pos[0] - 15, pos[1] + 15,
                -random.uniform(1, 3), random.uniform(-0.5, 0.5),
                random.choice(COLOR_TRAIL_PARTICLES),    # ← szín paraméter
                random.randint(3, 7),
                random.randint(20, 40)
            ))

    def emit_collision(self, pos):
        for _ in range(30):
            self.particles.append(Particle(
                pos[0], pos[1],
                random.uniform(-5, 5), random.uniform(-5, 5),
                random.choice(COLOR_SPARK_PARTICLES),    # ← szín paraméter
                random.randint(2, 5),
                random.randint(30, 60)
            ))

    def update_and_draw(self, surf, cam_off):
        self.particles = [p for p in self.particles if p.lifetime > 0]
        for p in self.particles:
            p.update()
        for p in self.particles:
            p.draw(surf, cam_off)


class ObstaclePair:
    def __init__(self, x, width, gap_y, gap_height):
        self.x = x
        self.width = width
        self.passed = False
        self.top_rect = pygame.Rect(x, 0, width, gap_y)
        self.bottom_rect = pygame.Rect(x, gap_y + gap_height, width,
                                       SCREEN_HEIGHT - (gap_y + gap_height))

    def draw(self, screen, cam_off):
        # 1. Árnyék réteg (előbb, alatta)
        pygame.draw.rect(screen, COLOR_OBSTACLE_SHADOW,
                         self.top_rect.move(-cam_off + 4, 4))
        pygame.draw.rect(screen, COLOR_OBSTACLE_SHADOW,
                         self.bottom_rect.move(-cam_off + 4, 4))

        # 2. Akadály réteg (felül)
        pygame.draw.rect(screen, COLOR_OBSTACLE,
                         self.top_rect.move(-cam_off, 0))
        pygame.draw.rect(screen, COLOR_OBSTACLE,
                         self.bottom_rect.move(-cam_off, 0))

    def collides_with(self, p_rect, cam_off):
        return (p_rect.colliderect(self.top_rect.move(-cam_off, 0)) or
                p_rect.colliderect(self.bottom_rect.move(-cam_off, 0)))

    def is_offscreen(self, cam_off):
        return self.x + self.width < cam_off


class Player:
    def __init__(self, x, y):
        self.x, self.y, self.size = x, y, 30
        self.target_y = SCREEN_HEIGHT - 100
        self.sprites = self._create_sprites()

    def _create_sprites(self):
        sprites = []
        for i in range(3):
            surf = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
            pygame.draw.circle(surf, COLOR_PLAYER,
                               (self.size // 2, self.size // 2), self.size // 2)
            pygame.draw.circle(surf, COLOR_PLAYER_EYE,
                               (self.size // 2 + 5, self.size // 2 - 5), 3)
            mouth_height = i * 4
            if mouth_height > 0:
                pygame.draw.ellipse(surf, COLOR_PLAYER_MOUTH,
                                    (self.size // 4, self.size // 2,
                                     self.size // 2, mouth_height))
            sprites.append(surf)
        return sprites

    def update(self, vol):
        self.target_y = SCREEN_HEIGHT - 100 - (vol * MAX_VOLUME_HEIGHT)
        self.y += (self.target_y - self.y) * PLAYER_SMOOTHNESS
        self.y = max(0, min(self.y, SCREEN_HEIGHT - self.size))
        if vol > 0.6:
            self.current_sprite = self.sprites[2]
        elif vol > 0.2:
            self.current_sprite = self.sprites[1]
        else:
            self.current_sprite = self.sprites[0]

    def draw(self, screen):
        screen.blit(self.current_sprite, (int(self.x - self.size // 2), int(self.y)))

    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.size, self.size)

# =============================================================================
# FŐ JÁTÉK OSZTÁLY
# =============================================================================

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("OBSTACLE")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)

        self.settings_panel = SettingsPanel(
            SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 150,
            300, 320, self.small_font
        )
        self.audio = AudioProcessor(self.settings_panel)
        self.sound_manager = SoundManager()
        self.adaptive_music = AdaptiveMusic(self.sound_manager)
        self.particle_system = ParticleSystem()
        self.background = ParallaxBackground()

        self.shake_intensity = 0
        self.shake_duration = 0
        self.game_state = "menu"
        self.reset_game()
        self.load_leaderboard()
        
        # Hullámforma pufferek és idők
        self.waveform_buffer = []
        self.last_waveform_update_time = time.time()
        # Ez határozza meg, hogy milyen gyakran frissül a hullámforma (másodpercben)
        # Próbáld meg 0.1-0.2 között, hogy lassabb legyen.
        self.waveform_update_interval = 0.07
        self.waveform_thickness = 8 # Új: hullámforma vastagság

    def _get_data_path(self, filename):
        """EXE és script módban is működő elérési út"""
        if getattr(sys, 'frozen', False):
            # PyInstaller EXE
            base_path = os.path.dirname(sys.executable)
        else:
            # Normál Python script
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, filename)
    
    def load_leaderboard(self):
        path = self._get_data_path("leaderboard.json")
        try:
            self.leaderboard = (
                json.load(open(path, "r", encoding="utf-8"))
                if os.path.exists(path) else []
            )
        except (json.JSONDecodeError, IOError):
            self.leaderboard = []
    
    def add_to_leaderboard(self, name, score):
        path = self._get_data_path("leaderboard.json")
        self.leaderboard.append({"name": name, "score": int(score)})
        self.leaderboard.sort(key=lambda x: x["score"], reverse=True)
        self.leaderboard = self.leaderboard[:10]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.leaderboard, f, ensure_ascii=False, indent=2)

    def get_difficulty_params(self):
        m = self.distance / DIFFICULTY_SCALE_DISTANCE
        gap = max(OBSTACLE_MIN_GAP * (GAP_REDUCTION_RATE ** m), MIN_GAP_SIZE)
        width = min(OBSTACLE_MIN_WIDTH * (WIDTH_INCREASE_RATE ** m), OBSTACLE_MAX_WIDTH)
        return gap, width

    def generate_obstacles(self):
        while self.last_obstacle_x < self.camera_offset + SCREEN_WIDTH + 200:
            gap_h, obs_w = self.get_difficulty_params()
            gap_y = np.random.randint(50, int(SCREEN_HEIGHT - gap_h - 50))
            self.obstacles.append(ObstaclePair(self.last_obstacle_x, obs_w, gap_y, gap_h))
            self.last_obstacle_x += (OBSTACLE_BASE_FREQUENCY
                                     + np.random.randint(-OBSTACLE_FREQUENCY_VARIANCE,
                                                         OBSTACLE_FREQUENCY_VARIANCE))
        self.obstacles = [obs for obs in self.obstacles if not obs.is_offscreen(self.camera_offset)]

    def check_obstacle_pass(self):
        player_center_x = self.player.x + self.camera_offset
        for obs in self.obstacles:
            if not obs.passed and obs.x + obs.width < player_center_x:
                obs.passed = True
                self.sound_manager.pass_obstacle_sound.play()

    def check_collisions(self):
        if self.invincible:
            return False
        player_rect = self.player.get_rect()
        for obs in self.obstacles:
            if obs.collides_with(player_rect, self.camera_offset):
                self.player_lives -= 1
                self.sound_manager.collision_sound.play()
                self.shake_intensity, self.shake_duration = 15, 20
                if self.player_lives <= 0:
                    return True
                else:
                    self.invincible = True
                    self.invincibility_timer = int(FPS * 1.5)
                    break
        return False

    def update_game_speed(self):
        self.game_speed = min(
            BASE_GAME_SPEED + (self.distance * SPEED_INCREASE_RATE),
            MAX_GAME_SPEED
        )

    # -------------------------------------------------------------------------
    # RAJZOLÓ METÓDUSOK
    # -------------------------------------------------------------------------

    def draw_menu(self):
        self.background.update(0, self.screen)
        self.background.draw(self.screen, 0)
        title = self.font.render("OBSTACLE", True, COLOR_TEXT_PRIMARY)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 80))
        instructions = [
            "Használd a hangodat a karakter irányításához!",
            "",
            "Nyomj SPACE-t a kezdéshez!",
            "Nyomj L-t a ranglistához!",
            "Nyomj S-t a beállításokhoz!",
        ]
        for i, line in enumerate(instructions):
            rendered = self.small_font.render(line, True, COLOR_TEXT_PRIMARY)
            self.screen.blit(rendered,
                             (SCREEN_WIDTH // 2 - rendered.get_width() // 2, 200 + i * 35))

    def draw_ui(self):
        dist_text = self.font.render(f"Távolság: {int(self.distance)}", True, COLOR_TEXT_PRIMARY)
        self.screen.blit(dist_text, (10, 10))
        lives_text = self.font.render(f"Életek: {self.player_lives}", True, COLOR_TEXT_PRIMARY)
        self.screen.blit(lives_text, (SCREEN_WIDTH - lives_text.get_width() - 10, 10))
        # ... (a draw_ui metódus után) ...

    def draw_volume_indicator(self, screen):
        # Paraméterek a sávokhoz
        bar_width = 20
        bar_height = 100
        padding = 10
        bottom_y = SCREEN_HEIGHT - padding

        # Hely a képernyő bal alsó részén
        x_pos_raw = padding
        x_pos_final = x_pos_raw + bar_width + padding * 3 # Távolabb helyezzük

        # ---- Nyers hangerő (Raw RMS) sáv ----
        raw_rms = self.audio.raw_rms
        scaled_raw_rms = np.clip(raw_rms * 10, 0, 1) # Skálázzuk, hogy jobban látszódjon
        
        # Sáv alapja
        pygame.draw.rect(screen, COLOR_SLIDER_BG, 
                         (x_pos_raw, bottom_y - bar_height, bar_width, bar_height))
        # Kitöltés
        fill_height_raw = scaled_raw_rms * bar_height
        pygame.draw.rect(screen, COLOR_BAR_RAW_FILL, 
                         (x_pos_raw, bottom_y - fill_height_raw, bar_width, fill_height_raw))

        # Küszöbszint jelző
        threshold_val = self.settings_panel.get_value("Threshold") * 0.05
        scaled_threshold = np.clip(threshold_val * 10, 0, 1) # Ugyanazzal a skálázással
        threshold_y = bottom_y - (scaled_threshold * bar_height)
        pygame.draw.line(screen, COLOR_BAR_THRESHOLD, 
                         (x_pos_raw, threshold_y), 
                         (x_pos_raw + bar_width, threshold_y), 2)
        
        # Címke
        raw_label = self.small_font.render("RAW", True, COLOR_TEXT_SECONDARY)
        screen.blit(raw_label, (x_pos_raw + bar_width // 2 - raw_label.get_width() // 2, bottom_y - bar_height - raw_label.get_height() - 5))


        # ---- Végső hangerő (Final Volume) sáv ----
        final_volume = self.audio.get_volume()
        
        # Sáv alapja
        pygame.draw.rect(screen, COLOR_SLIDER_BG, 
                         (x_pos_final, bottom_y - bar_height, bar_width, bar_height))
        # Kitöltés
        fill_height_final = final_volume * bar_height
        pygame.draw.rect(screen, COLOR_BAR_FINAL_FILL, 
                         (x_pos_final, bottom_y - fill_height_final, bar_width, fill_height_final))

        # Címke
        final_label = self.small_font.render("FINAL", True, COLOR_TEXT_SECONDARY)
        screen.blit(final_label, (x_pos_final + bar_width // 2 - final_label.get_width() // 2, bottom_y - bar_height - final_label.get_height() - 5))

    # ... (a többi metódus) ...
    
    def draw_waveform(self, surf):
            # Módosítás itt: csak akkor frissítjük a puffert, ha eljött az ideje
            current_time = time.time()
            if current_time - self.last_waveform_update_time >= self.waveform_update_interval:
                # Csak akkor adjuk hozzá a legfrissebb adatot a pufferhez
                # ha elég idő telt el a legutóbbi frissítés óta.
                self.waveform_buffer = list(self.audio.waveform_data) # Másolatot készítünk
    
                # Esetleg simíthatjuk is a waveform_buffer-t, ha túl szaggatottnak tűnik
                # (opcionális, ha szükséges)
                # if len(self.waveform_buffer) > 1:
                #     # Egyszerű mozgóátlag simítás
                #     window_size = 5 # Kísérletezni kell vele
                #     self.waveform_buffer = np.convolve(self.waveform_buffer, np.ones(window_size)/window_size, mode='valid')
    
                self.last_waveform_update_time = current_time
    
            points = []
            # Most a puffelt adatot használjuk, nem közvetlenül az audio.waveform_data-t
            data = self.waveform_buffer
            if not data: # Ha még nincs adat a pufferben
                return
    
            # A hullámforma szélessége a teljes képernyőszélesség legyen
            # Ha a vizuális indikátor miatt ütközne, akkor itt kell állítani a start_x-et
            start_x = 100
            end_x = SCREEN_WIDTH-100
    
            # A step értékét a buffer méretéhez és a megjelenítési szélességhez igazítjuk
            # A cél az, hogy a 'data' minden elemét figyelembe vegyük, de ne rajzoljunk több pontot, mint amennyi pixel van
            step = max(1, len(data) // (end_x - start_x))
            if step == 0: # Megelőzés a nulla osztás ellen, ha data nagyon kicsi
                step = 1
    
            for i in range(0, len(data), step):
                x_coord = start_x + (i / len(data)) * (end_x - start_x)
                # A hullámforma Y pozíciója az aljától számítva.
                # Az adatot szorozzuk 150-nel, hogy láthatóbb legyen az ingadozás.
                y_coord = SCREEN_HEIGHT - 50 - (data[i] * 150)
                points.append((x_coord, y_coord))
    
            if len(points) > 1:
                color = COLOR_WAVEFORM_LOW.lerp(COLOR_WAVEFORM_HIGH, self.audio.get_volume())
                # Vastagság hozzáadva a draw.aalines hívásához
                pygame.draw.lines(surf, color, False, points, self.waveform_thickness)
                # pygame.draw.aalines(surf, color, False, points, self.waveform_thickness)

    def draw_game(self, render_offset=(0, 0)):
        self.background.update(self.distance, self.screen)
        self.background.draw(self.screen, self.camera_offset)
        offset_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.particle_system.update_and_draw(offset_surface, self.camera_offset)
        for obs in self.obstacles:
            obs.draw(offset_surface, self.camera_offset)
        if not (self.invincible and self.invincibility_timer % 10 < 5):
            self.player.draw(offset_surface)
        self.screen.blit(offset_surface, render_offset)
        self.draw_waveform(self.screen)
        self.draw_volume_indicator(self.screen) # Új elem, a bal alsó sarokban
        self.draw_ui()

    def draw_game_over(self, render_offset=(0, 0)):
        self.background.update(self.distance, self.screen)
        self.background.draw(self.screen, self.camera_offset)
        offset_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.particle_system.update_and_draw(offset_surface, self.camera_offset)
        self.screen.blit(offset_surface, render_offset)

        go_text = self.font.render("GAME OVER!", True, COLOR_TEXT_DANGER)
        self.screen.blit(go_text, (SCREEN_WIDTH // 2 - go_text.get_width() // 2, 150))

        dist_text = self.font.render(f"Távolság: {int(self.distance)}", True, COLOR_TEXT_PRIMARY)
        self.screen.blit(dist_text, (SCREEN_WIDTH // 2 - dist_text.get_width() // 2, 220))

        name_prompt = self.small_font.render("Add meg a neved:", True, COLOR_TEXT_PRIMARY)
        self.screen.blit(name_prompt, (SCREEN_WIDTH // 2 - name_prompt.get_width() // 2, 290))

        pygame.draw.rect(self.screen, COLOR_TEXT_PRIMARY, (250, 330, 300, 40), 2)
        name_render = self.font.render(self.player_name + "_", True, COLOR_TEXT_PRIMARY)
        self.screen.blit(name_render, (260, 335))

    def draw_leaderboard(self):
        self.background.update(0, self.screen)
        self.background.draw(self.screen, 0)

        title = self.font.render("🏆 RANGLISTA 🏆", True, COLOR_TEXT_HIGHLIGHT)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 30))

        medals = ['🥇', '🥈', '🥉']
        for i, entry in enumerate(self.leaderboard[:10]):
            prefix = medals[i] if i < 3 else f"{i + 1}."
            color = COLOR_RANK_TOP3 if i < 3 else COLOR_RANK_DEFAULT
            line = f"{prefix} {entry['name']}: {entry['score']}"
            rendered = self.small_font.render(line, True, color)
            self.screen.blit(rendered, (SCREEN_WIDTH // 2 - rendered.get_width() // 2, 100 + i * 40))

        esc_text = self.small_font.render("Nyomj ESC-et a menühöz", True, COLOR_TEXT_PRIMARY)
        self.screen.blit(esc_text, (SCREEN_WIDTH // 2 - esc_text.get_width() // 2, 520))

    def reset_game(self):
        self.player = Player(150, SCREEN_HEIGHT - 100)
        self.obstacles = []
        self.camera_offset = 0
        self.distance = 0
        self.game_over = False
        self.game_speed = BASE_GAME_SPEED
        self.last_obstacle_x = OBSTACLE_START_DISTANCE
        self.particle_system.particles.clear() if hasattr(self, 'particle_system') else None
        self.player_name = ""
        self.player_lives = INITIAL_PLAYER_LIVES
        self.invincible = False
        self.invincibility_timer = 0

    # -------------------------------------------------------------------------
    # FŐ JÁTÉK LOOP
    # -------------------------------------------------------------------------

    def run(self):
        self.audio.start()
        running = True
        try:
            while running:
                self.clock.tick(FPS)

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    if self.game_state == "settings":
                        self.settings_panel.handle_event(event)
                    if event.type == pygame.KEYDOWN:
                        if self.game_state == "menu" and event.key == pygame.K_SPACE:
                            self.reset_game()
                            self.game_state = "playing"
                        elif self.game_state == "menu" and event.key == pygame.K_l:
                            self.game_state = "leaderboard"
                        elif self.game_state == "menu" and event.key == pygame.K_s:
                            self.game_state = "settings"
                        elif self.game_state == "settings" and event.key == pygame.K_ESCAPE:
                            self.game_state = "menu"
                        elif (self.game_state == "game_over"
                              and event.key == pygame.K_RETURN
                              and self.player_name):
                            self.add_to_leaderboard(self.player_name, self.distance)
                            self.game_state = "leaderboard"
                        elif self.game_state == "game_over" and event.key == pygame.K_BACKSPACE:
                            self.player_name = self.player_name[:-1]
                        elif (self.game_state == "game_over"
                              and len(self.player_name) < 15
                              and (event.unicode.isalnum() or event.unicode == " ")):
                            self.player_name += event.unicode
                        elif event.key == pygame.K_ESCAPE:
                            self.game_state = "menu"

                self.audio.process_audio()

                render_offset = (
                    (random.randint(-self.shake_intensity, self.shake_intensity),
                     random.randint(-self.shake_intensity, self.shake_intensity))
                    if self.shake_duration > 0 else (0, 0)
                )
                if self.shake_duration > 0:
                    self.shake_duration -= 1

                if self.game_state == "playing":
                    # Debug kimenetek
                    print(f"Obstacles: {len(self.obstacles)}, "
                          f"Any passed: {any(o.passed for o in self.obstacles)}, "
                          f"Volume: {self.audio.get_volume():.2f}, "
                          f"Invincible: {self.invincible}, "
                          f"Mixer init: {pygame.mixer.get_init()}")
                    print(f"Raw RMS: {self.audio.raw_rms:.6f}, "
                          f"Stream active: {self.audio.stream is not None and self.audio.stream.active}, "
                          f"Queue size: {self.audio.audio_queue.qsize()}")

                    if self.invincible:
                        self.invincibility_timer -= 1
                        if self.invincibility_timer <= 0:
                            self.invincible = False

                    self.player.update(self.audio.get_volume())
                    self.particle_system.emit_trail((self.player.x + self.camera_offset, self.player.y))
                    self.camera_offset += self.game_speed
                    self.distance += self.game_speed / 10
                    self.generate_obstacles()
                    self.update_game_speed()
                    self.check_obstacle_pass()
                    self.adaptive_music.update(self.game_speed, self.obstacles, self.camera_offset)

                    if self.check_collisions():
                        self.game_state = "game_over"

                # Állapot alapú rajzolás
                if self.game_state == "playing":
                    self.draw_game(render_offset)
                elif self.game_state == "game_over":
                    self.draw_game_over(render_offset)
                elif self.game_state == "menu":
                    self.draw_menu()
                elif self.game_state == "leaderboard":
                    self.draw_leaderboard()
                elif self.game_state == "settings":
                    self.draw_menu()
                    self.settings_panel.draw(self.screen, self.audio.raw_rms, self.audio.get_volume())

                pygame.display.flip()
        finally:
            self.audio.stop()
            pygame.quit()


if __name__ == "__main__":
    game = Game()
    game.run()