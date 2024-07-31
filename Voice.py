from enum import Enum
import abc
import os
import threading
import feature_support
import pyttsx3
import numpy as np
import time
if feature_support.espeak_supported:
	import espeakng
if feature_support.coqui_supported:
	from TTS.api import TTS
	from TTS.utils import manage

class Voice(abc.ABC):
	class VoiceType(Enum):
		ESPEAK = ("ESpeak", feature_support.espeak_supported)
		COQUI = ("Coqui TTS", feature_support.coqui_supported)
		SYSTEM = ("System Voices", True)

	def __new__(cls, voice_type, init_args=[], name="Unnamed"):
		if cls is Voice:
			if voice_type == cls.VoiceType.ESPEAK:
				return super().__new__(ESpeakVoice)
			elif voice_type == cls.VoiceType.COQUI:
				return super().__new__(CoquiVoice)
			elif voice_type == cls.VoiceType.SYSTEM:
				return super().__new__(SystemVoice)
		else:
			return super().__new__(cls)

	def __init__(self, voice_type, init_args=[], name="Unnamed"):
		self.voice = None
		self.voice_type = voice_type
		self.name = name
		self.voice_option = None

	@abc.abstractmethod
	def speak(self, text, file_name):
		pass

	def set_speed(self, speed):
		pass

	@abc.abstractmethod
	def set_voice_params(self, voice=None, pitch=None):
		pass

	@abc.abstractmethod
	def list_voice_options(self):
		pass

	def calibrate_rate(self):
		output_path = './output/calibration.wav'
		calibration_phrase_long = "In the early morning light, a vibrant scene unfolds as the quick brown fox jumps gracefully over the lazy dog. The fox's russet fur glistens in the sun, and its swift movements captivate onlookers. With a leap of agility, it soars through the air, showcasing its remarkable prowess. Meanwhile, the dog, relaxed and unperturbed, watches with half-closed eyes, acknowledging the fox's spirited display. The surrounding nature seems to hold its breath, enchanted by this charming spectacle. The gentle rustling of leaves and the distant chirping of birds provide a soothing soundtrack to this magical moment. The two animals, one lively and the other laid-back, showcase the beautiful harmony of nature, an ageless dance that continues to mesmerize all who witness it."
		calibration_phrase_chair = "A chair is a piece of furniture with a raised surface used to sit on, commonly for use by one person. Chairs are most often supported by four legs and have a back; however, a chair can have three legs or could have a different shape. A chair without a back or arm rests is a stool, or when raised up, a bar stool."
		calibration_phrase = "Hello? Testing, testing. Is.. is this thing on? Ah! Hello Gordon! I'm... assuming that's your real name... You wouldn't lie to us. Would you? Well... You finally did it! You survived the resonance cascade! You brought us all to hell and back, alive! You made it to the ultimate birthday bash at the end of the world! You beat the video game! And... now I imagine you'll... shut it down. Move on with your life. Onwards and upwards, ay Gordon? I don't.. know... how much longer I have to send this to you so I'll try to keep it brief. Not my specialty. Perhaps this is presumptuous of me but... Must this really be the end of our time together? Perhaps you could take the science team's data, transfer us somewhere else, hmm? Now... it doesn't have to be Super Punch-Out for the Super Nintendo Entertainment System. Maybe a USB drive, or a spare floppy disk. You could take us with you! We could see the world! We could... I'm getting a little ahead of myself, surely. Welp! The option's always there! You changed our lives, Gordon. I'd like to think it was for the better. And I don't know what's going to happen to us once you exit the game for good. But I know we'll never forget you. I hope you won't forget us. Well... This is where I get off. Goodbye Gordon!"
		self.speak(calibration_phrase, output_path)

	def get_wpm(words, duration):
		return (len(words.split(' ')) / duration * 60)

class ESpeakVoice(Voice):
	def __init__(self, init_args=[], name="Unnamed"):
		super().__init__(Voice.VoiceType.ESPEAK, init_args, name)
		self.voice = espeakng.Speaker()
		self.voice_option = self.voice.voice

	def speak(self, text, file_name):
		self.voice.say(text, wait4prev=True, export_path=file_name)
		time.sleep(0.1) # We need to replace this with something that actually checks if the command output is finished tbh
		return file_name

	def set_voice_params(self, voice=None, pitch=None):
		if voice:
			self.voice.voice = self.voice_option = voice
		if pitch:
			self.voice.pitch = pitch

	def list_voice_options(self):
		return ["af","sq","am","ar","an","hy","hyw","as","az","ba","cu","eu","be","bn","bpy","bs","bg","my","ca","chr","yue","hak","haw","cmn","hr","cs","da","nl","en-us","en","en-029","en-gb-x-gbclan","en-gb-x-rp","en-gb-scotland","en-gb-x-gbcwmd","eo","et","fa","fa-latn","fi","fr-be","fr","fr-ch","ga","gd","ka","de","grc","el","kl","gn","gu","ht","he","hi","hu","is","id","ia","io","it","ja","kn","kok","ko","ku","kk","ky","la","lb","ltg","lv","lfn","lt","jbo","mi","mk","ms","ml","mt","mr","nci","ne","nb","nog","or","om","pap","py","pl","pt-br","qdb","qu","quc","qya","pt","pa","piqd","ro","ru","ru-lv","uk","sjn","sr","tn","sd","shn","si","sk","sl","smj","es","es-419","sw","sv","ta","th","tk","tt","te","tr","ug","ur","uz","vi-vn-x-central","vi","vi-vn-x-south","cy"]

class CoquiVoice(Voice):
	def __init__(self, init_args=None, name="Coqui Voice"):
		super().__init__(Voice.VoiceType.COQUI, init_args, name)
		self.voice = TTS().to('cuda' if feature_support.gpu_supported else 'cpu')
		self.langs = ["All Languages"] + list({lang.split("/")[1] for lang in self.voice.models})
		self.langs.sort()
		self.selected_lang = 'en'
		self.is_multispeaker = False
		self.speaker = None
		self.is_clonable = False
		self.use_vc = False
		self.speaker_wav = ""
	def speak(self, text, file_path=None):
		if file_path:
			if not self.use_vc or "xtts" in self.voice.model_name:
				return self.voice.tts_to_file(
					text,
					file_path=file_path,
					speaker=self.speaker,
					language='en' if self.voice.is_multi_lingual else None,
					speaker_wav=self.speaker_wav
				)
			else:
				self.voice.tts_with_vc_to_file(
					text,
					file_path=file_path,
					speaker=self.speaker,
					language='en' if self.voice.is_multi_lingual else None,
					speaker_wav=self.speaker_wav
				)
				return file_path
		else:
			return np.array(self.voice.tts(
				text,
				speaker=self.speaker,
				language= 'en' if self.voice.is_multi_lingual else None,
				speaker_wav=self.speaker_wav
			))

	def set_voice_params(self, voice=None, speaker=None, speaker_wav=None, use_vc=None, progress=None):
		if voice and voice != self.voice_option:
			if progress:
				progress(0, "downloading")
				download_thread = threading.Thread(target=self.voice.load_tts_model_by_name, args=(voice,))
				download_thread.start()
				while(download_thread.is_alive()):
					# I'll remove this check if they accept my PR c:
					bar = manage.ModelManager.tqdm_progress if hasattr(manage.ModelManager, "tqdm_progress") else None
					if bar:
						progress_value = int(100*(bar.n / bar.total))
						progress(progress_value, "downloading")
					time.sleep(0.25)  # Adjust the interval as needed
				progress(-1, "done!")
			else:
				self.voice.load_tts_model_by_name(voice)
			self.voice_option = self.voice.model_name
		self.is_multispeaker = self.voice.is_multi_speaker
		if "xtts" in self.voice.model_name or self.use_vc:
			self.is_clonable = True
			# self.is_multispeaker = False
		if use_vc is not None:
			self.use_vc = use_vc
		if speaker_wav is not None:
			self.speaker_wav = speaker_wav
		if speaker is not None:
			self.speaker = speaker
			if "xtts" in self.voice.model_name and self.use_vc:
				self.speaker = None

	def list_voice_options(self):
		return self.voice.models

	def is_model_downloaded(self, model_name):
		return os.path.exists(os.path.join(self.voice.manager.output_prefix, self.voice.manager._set_model_item(model_name)[1]))

	def list_speakers(self):
		return self.voice.speakers if self.voice.is_multi_speaker else []

class SystemVoice(Voice):
	def __init__(self, init_args=[], name="Unnamed"):
		super().__init__(Voice.VoiceType.SYSTEM, init_args, name)
		self.voice = pyttsx3.init()
		self.voice_option = self.voice.getProperty('voice')

	def speak(self, text, file_name):
		self.voice.save_to_file(text, file_name)
		self.voice.runAndWait()
		return file_name

	def set_speed(self, speed):
		self.voice.setProperty('rate', speed)

	def set_voice_params(self, voice=None, pitch=None):
		if voice:
			print(voice, self.voice.getProperty('voices')[self.list_voice_options().index(voice)].id)
			self.voice.setProperty('voice', self.voice.getProperty('voices')[self.list_voice_options().index(voice)].id)
			self.voice_option = voice # self.voice.getProperty('voice')

	def list_voice_options(self):
		return [voice.name for voice in self.voice.getProperty('voices')]
