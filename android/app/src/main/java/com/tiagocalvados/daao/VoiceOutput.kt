package com.tiagocalvados.daao

interface VoiceOutput {
    fun speak(text: String, onFinished: (String?) -> Unit)
    fun stop()
    fun shutdown()
}
