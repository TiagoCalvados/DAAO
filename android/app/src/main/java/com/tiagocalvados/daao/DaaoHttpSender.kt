package com.tiagocalvados.daao

import java.net.HttpURLConnection
import java.net.URI

data class SendResult(
    val statusCode: Int,
    val responseText: String,
)

object DaaoHttpSender {
    fun send(endpoint: URI, body: MultipartBody): SendResult {
        val connection = endpoint.toURL().openConnection() as HttpURLConnection
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 4_000
            connection.readTimeout = 4_000
            connection.instanceFollowRedirects = false
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", body.contentType)
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("User-Agent", "DAAO-Android/0.3.3")
            connection.setFixedLengthStreamingMode(body.bytes.size)
            connection.outputStream.use { it.write(body.bytes) }

            val status = connection.responseCode
            val response =
                (if (status in 200..299) connection.inputStream else connection.errorStream)
                    ?.bufferedReader()
                    ?.use { it.readText() }
                    .orEmpty()
            return SendResult(status, response)
        } finally {
            connection.disconnect()
        }
    }
}
