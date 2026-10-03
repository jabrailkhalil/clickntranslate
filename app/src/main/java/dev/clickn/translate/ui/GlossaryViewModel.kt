// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dev.clickn.translate.appcontext.ForegroundApp
import dev.clickn.translate.appcontext.ForegroundAppResolver
import dev.clickn.translate.appcontext.InstalledAppCatalog
import dev.clickn.translate.appcontext.SelectableApp
import dev.clickn.translate.data.SettingsRepository
import dev.clickn.translate.glossary.GlossaryTermEntity
import dev.clickn.translate.glossary.GlossaryImportCommitResult
import dev.clickn.translate.glossary.GlossaryImportConflictPolicy
import dev.clickn.translate.glossary.TranslationGlossaryRepository
import dev.clickn.translate.translate.TranslationMemoryRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

@HiltViewModel
class GlossaryViewModel @Inject constructor(
    private val glossaryRepository: TranslationGlossaryRepository,
    private val foregroundAppResolver: ForegroundAppResolver,
    private val installedAppCatalog: InstalledAppCatalog,
    private val settingsRepository: SettingsRepository,
    private val translationMemoryRepository: TranslationMemoryRepository,
) : ViewModel() {
    init {
        viewModelScope.launch { glossaryRepository.ensureSourcePreservationPresets() }
    }

    val terms = glossaryRepository.observeAll().stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = emptyList(),
    )

    val memories = translationMemoryRepository.observeAll().stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = emptyList(),
    )

    val sourcePreservationEnabled: StateFlow<Boolean?> = settingsRepository.settings
        .map { settings -> settings.sourcePreservationEnabled }
        .distinctUntilChanged()
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5_000),
            initialValue = null,
        )

    suspend fun currentApp(): ForegroundApp? {
        val settings = settingsRepository.get()
        return foregroundAppResolver.resolve(settings.foregroundAppDetectionMode)
    }

    val glossaryEnabled: StateFlow<Boolean?> = settingsRepository.settings
        .map { it.translationGlossaryEnabled }
        .distinctUntilChanged()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    val memoryEnabled: StateFlow<Boolean?> = settingsRepository.settings
        .map { it.translationMemoryEnabled }
        .distinctUntilChanged()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    fun setGlossaryEnabled(enabled: Boolean) {
        viewModelScope.launch {
            settingsRepository.update { it.copy(translationGlossaryEnabled = enabled) }
        }
    }

    fun setMemoryEnabled(enabled: Boolean) {
        viewModelScope.launch {
            settingsRepository.update { it.copy(translationMemoryEnabled = enabled) }
        }
    }

    suspend fun defaultLanguages(): Pair<String, String> {
        val settings = settingsRepository.get()
        return settings.sourceLang to settings.targetLang
    }

    suspend fun selectableApps(): List<SelectableApp> = installedAppCatalog.launchableApps()

    suspend fun upsert(term: GlossaryTermEntity): Long = glossaryRepository.upsert(term)

    suspend fun findConflict(term: GlossaryTermEntity): GlossaryTermEntity? =
        glossaryRepository.findConflict(term)

    suspend fun overwriteConflict(term: GlossaryTermEntity): Long =
        glossaryRepository.overwriteConflict(term)

    suspend fun importTerms(
        terms: List<GlossaryTermEntity>,
        conflictPolicy: GlossaryImportConflictPolicy,
    ): GlossaryImportCommitResult = glossaryRepository.importUserTerms(terms, conflictPolicy)

    suspend fun delete(id: Long) = glossaryRepository.delete(id)

    fun setSourcePreservationEnabled(enabled: Boolean) {
        viewModelScope.launch {
            settingsRepository.update { settings ->
                settings.copy(sourcePreservationEnabled = enabled)
            }
        }
    }

    suspend fun updateMemory(
        id: Long,
        correctedSource: String,
        correctedTranslation: String,
    ): Boolean = translationMemoryRepository.updateCorrection(
        id = id,
        correctedSource = correctedSource,
        correctedTranslation = correctedTranslation,
    )

    suspend fun deleteMemory(id: Long) = translationMemoryRepository.delete(id)
}
