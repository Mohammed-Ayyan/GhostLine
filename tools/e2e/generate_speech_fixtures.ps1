Add-Type -AssemblyName System.Speech

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile("$PSScriptRoot/../../tests/fixtures/speech_6s.wav")
$synth.Speak("In computer science, a binary search tree is a rooted binary tree data structure whose internal nodes each store a key.")
$synth.Dispose()

$synth2 = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth2.SetOutputToWaveFile("$PSScriptRoot/../../tests/fixtures/speech_20s.wav")
$synth2.Speak("The quick brown fox jumps over the lazy dog. In computer science, an abstract data type is a mathematical model for data types. Many algorithms rely on efficient searching and sorting techniques to process massive datasets in modern distributed web systems.")
$synth2.Dispose()

$synth3 = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth3.SetOutputToWaveFile("$PSScriptRoot/../../tests/fixtures/question_bst.wav")
$synth3.Speak("What is the time complexity of searching in a balanced binary search tree?")
$synth3.Dispose()

Write-Host "Generated speech fixtures successfully."

