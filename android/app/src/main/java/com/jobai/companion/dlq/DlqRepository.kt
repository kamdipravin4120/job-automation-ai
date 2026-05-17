package com.jobai.companion.dlq

import com.jobai.companion.core.api.JobAiService
import com.jobai.companion.core.db.DlqDao
import com.jobai.companion.core.db.DlqEntity
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.Instant
import javax.inject.Inject
import javax.inject.Singleton

data class DlqItem(
    val id: String,
    val kind: String,
    val status: String,
    val errorCode: String?,
    val retryCount: Int,
    val startedAt: Instant?,
)

@Singleton
class DlqRepository @Inject constructor(
    private val dlqDao: DlqDao,
    private val api: JobAiService,
) {
    val dlqFlow: Flow<List<DlqItem>> = dlqDao.observeAll().map { entities ->
        entities.map {
            DlqItem(
                id = it.id,
                kind = it.kind,
                status = it.status,
                errorCode = it.errorCode,
                retryCount = it.retryCount,
                startedAt = it.startedAt?.let(Instant::ofEpochMilli),
            )
        }
    }

    suspend fun sync() {
        val now = System.currentTimeMillis()
        val resp = api.listDlq()
        dlqDao.upsertAll(resp.items.map { dto ->
            DlqEntity(
                id = dto.id,
                kind = dto.kind,
                correlationId = dto.correlationId,
                status = dto.status,
                errorCode = dto.errorCode,
                retryCount = dto.retryCount,
                startedAt = dto.startedAt?.let { Instant.parse(it).toEpochMilli() },
                finishedAt = dto.finishedAt?.let { Instant.parse(it).toEpochMilli() },
                syncedAt = now,
            )
        })
    }

    suspend fun retry(itemId: String) {
        runCatching { api.retryDlqItem(itemId) }
        sync()
    }

    suspend fun dismiss(itemId: String) {
        runCatching { api.dismissDlqItem(itemId) }
        dlqDao.delete(itemId)
    }
}
