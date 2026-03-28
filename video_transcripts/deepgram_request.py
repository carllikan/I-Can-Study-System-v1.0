from deepgram import DeepgramClient, PrerecordedOptions 
 
DEEPGRAM_API_KEY = '0b4882c87b2529ec4a54b2a9d1a06e181a81b56d' 
 
AUDIO_URL = { 
  'url': 'E:\Addaxis\ICS\video_transcripts\Live Clinic 21.mp3' 
}
 
def main(): 
  try: 
    deepgram = DeepgramClient(DEEPGRAM_API_KEY) 
 
    options = PrerecordedOptions(
      model="nova-2", 
      language="en", 
      smart_format=True, 
      punctuate=True, 
      keywords=['eisenhower matrix:10', 
                    "urgency trapping:10",
                    "consequentialism:10",
                    "PB:10",
                    "BEDS-M:10",
                    "motivation enhanced mindset:10",
                    "reversion response awareness:10",
                    "misinterpreted effort:10",
                    "learning zone:10",
                    "Spaced interleaved retrieval:10",
                    "Marginal gains tracking:10",
                    "Prestudy:10",
                    "non-linear note-taking:10",
                    "desirable difficulty:10",
                    "basics of microlearning:10",
                    "Grouping information based on similarities:10",
                    "Kolbs:10",
                    "TLS:10",
                    "order control:10",
                    "Prioritising chunks to form backbone:10",
                    "Goal setting guidelines:10",
                    "risk management:10",
                    "loss aversion:10",
                    "Aim step:10",
                    "environmental optimisation:10",
                    "intention setting:10",
                    "ritualisation:10",
                    "CSP:10",
                    "Shoot step:10",
                    "layers of learning:10",
                    "Skin step:10",
                    "sufficient chunking:10",
                    "intuitive chunking:10",
                    "GRINDE:10",
                    "Hipshot:10",
                    "Reverse goal setting:10",
                    "growth vs fixed mindset,:10",
                    "neuroticism awareness:10",
                    "focus training:10",
                    "PEER:10",
                    "habit building guidelines:10",
                    "Priority 0+1:10",
                    "OFF-rest timing:10",
                    "active relaxation:10",
                    "MMoL:10",
                    "active flashcard management:10",
                    "true recall:10",
                    "Revision guidelines:10",
                    "WPW:10",
                    "Eat the frog:10",
                    "2 min rule:10",
                    "bottlenecks:10",
                    "Decisional delays:10",
                    "attention management:10",
                    "intention awareness:10",
                    "flow state:10",
                    "Parkinson's law:10",
                    "Multi-pass:10",
                    "Psychological state:10",
                    "application adjustment:10",
                    "silly-mistake syndome:10",
                    "MR FIG:10",
                    "diet and sleep:10",
                    "reCOVer:10",
                    "V-ABC framework:10",
                    "Medication:10",
                    "Focus training:10",
                    "physical cues:10",
                    "marginal gains tracking:10",
                    "Further Kolb's guidelines:10",
                    "Further environmental optimisation:10"
                    ], 
    ) 
 
    response = deepgram.listen.prerecorded.v('1').transcribe_url(AUDIO_URL, options) 
    print(response) 
 
  except Exception as e: 
    print(f'Exception: {e} ') 
 
if __name__ == '__main__': 
  main()