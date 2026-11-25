package dev.clickn.translate.history

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Index
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "text_history", indices = [Index(value = ["createdAtMs"])])
data class TextHistoryEntry(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val createdAtMs: Long,
    val source: String,
    val translated: String,
    val from: String,
    val to: String,
    val provider: String,
)

/** A durable import receipt and clear generation; legacy preferences are never the live store. */
@Entity(tableName = "text_history_state")
data class TextHistoryStoreState(
    @PrimaryKey val id: Int = 1,
    val legacyImported: Boolean = false,
    val generation: Long = 0,
    val legacyErasePending: Boolean = false,
)

@Dao
interface TextHistoryDao {
    @Query("SELECT * FROM text_history ORDER BY createdAtMs DESC, id DESC")
    fun observeAll(): Flow<List<TextHistoryEntry>>

    @Query("SELECT * FROM text_history ORDER BY createdAtMs DESC, id DESC")
    suspend fun listAll(): List<TextHistoryEntry>

    @Query("SELECT * FROM text_history_state WHERE id = 1")
    suspend fun state(): TextHistoryStoreState?

    @Query("SELECT * FROM text_history_state WHERE id = 1")
    fun observeState(): Flow<TextHistoryStoreState?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun putState(state: TextHistoryStoreState)

    @Insert
    suspend fun insert(entry: TextHistoryEntry): Long

    @Query("SELECT EXISTS(SELECT 1 FROM text_history WHERE createdAtMs = :createdAtMs " +
        "AND source = :source AND translated = :translated AND `from` = :from AND `to` = :to AND provider = :provider)")
    suspend fun contains(createdAtMs: Long, source: String, translated: String, from: String, to: String, provider: String): Boolean

    @Query("DELETE FROM text_history WHERE source = :source AND `from` = :from AND `to` = :to AND provider = :provider")
    suspend fun deletePrevious(source: String, from: String, to: String, provider: String)

    @Query("DELETE FROM text_history")
    suspend fun deleteAll()
}

@Database(entities = [TextHistoryEntry::class, TextHistoryStoreState::class], version = 1, exportSchema = false)
abstract class TextHistoryDatabase : RoomDatabase() {
    abstract fun historyDao(): TextHistoryDao
}
