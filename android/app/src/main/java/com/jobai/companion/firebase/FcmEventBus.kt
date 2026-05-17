package com.jobai.companion.firebase

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

data class FcmEvent(val kind: String, val jobId: String?)

object FcmEventBus {
    private val _events = MutableSharedFlow<FcmEvent>(extraBufferCapacity = 8)
    val events: SharedFlow<FcmEvent> = _events.asSharedFlow()
    fun emit(event: FcmEvent) { _events.tryEmit(event) }
}
