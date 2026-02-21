import pyttsx3

engine = pyttsx3.init()

engine.setProperty('rate', 160)   # speed
engine.setProperty('volume', 1.0) # volume

text = "Please confirm your date of birth."

engine.say(text)
engine.runAndWait()
