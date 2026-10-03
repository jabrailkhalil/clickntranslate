// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dev.clickn.translate.data.DictionaryLookupMode
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.SettingsRepository
import dev.clickn.translate.dictionary.DictionaryPackId
import dev.clickn.translate.dictionary.DictionaryPackInstallResult
import dev.clickn.translate.dictionary.DictionaryPackInstaller
import dev.clickn.translate.dictionary.DictionaryPackStatus
import dev.clickn.translate.dictionary.supportsOnlineDictionaryLookup
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

@HiltViewModel
class DictionaryLibraryViewModel @Inject constructor(
    private val settingsRepository: SettingsRepository,
    private val installer: DictionaryPackInstaller,
) : ViewModel() {
    val settings: StateFlow<Settings> = settingsRepository.settings.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = Settings(),
    )

    private val _packStatuses = MutableStateFlow<List<DictionaryPackStatus>>(emptyList())
    val packStatuses: StateFlow<List<DictionaryPackStatus>> = _packStatuses

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch { _packStatuses.value = installer.statuses() }
    }

    suspend fun selectMode(mode: DictionaryLookupMode): Boolean {
        val current = settingsRepository.get()
        if (mode == DictionaryLookupMode.ONLINE &&
            !supportsOnlineDictionaryLookup(current.translatorEngine)
        ) {
            return false
        }
        settingsRepository.update { it.copy(dictionaryLookupMode = mode) }
        return true
    }

    fun setTapLookupEnabled(enabled: Boolean) {
        viewModelScope.launch {
            settingsRepository.update { it.copy(dictionaryTapLookupEnabled = enabled) }
        }
    }

    suspend fun importPack(uri: Uri, id: DictionaryPackId): DictionaryPackInstallResult {
        val result = installer.importPack(
            uri = uri,
            expectedId = id,
        )
        _packStatuses.value = installer.statuses()
        return result
    }

    suspend fun deletePack(id: DictionaryPackId): Boolean {
        val deleted = installer.delete(id)
        _packStatuses.value = installer.statuses()
        return deleted
    }
}
