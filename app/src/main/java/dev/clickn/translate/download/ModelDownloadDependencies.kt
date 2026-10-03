// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.download

import dev.clickn.translate.data.MangaOcrModelPolicy

/** The same dependency graph is used for scheduling, recovery and readiness. */
object ModelDownloadDependencies {
    fun directDependencies(spec: ModelDownloadSpec): List<ModelDownloadSpec> = when (spec.type) {
        ModelDownloadType.MANGA_OCR -> listOf(
            ModelDownloadSpec.paddle(MangaOcrModelPolicy.recommendedDetectorVersion),
        )
        else -> emptyList()
    }

    /** Dependencies precede their consumers; repeated requests never duplicate an artifact. */
    fun expand(specs: List<ModelDownloadSpec>): List<ModelDownloadSpec> {
        val ordered = linkedSetOf<ModelDownloadSpec>()
        fun visit(spec: ModelDownloadSpec) {
            if (spec in ordered) return
            directDependencies(spec).forEach(::visit)
            ordered += spec
        }
        specs.forEach(::visit)
        return ordered.toList()
    }

    /** Independent models stay parallel, but consumers and shared dependencies stay in one work. */
    fun independentRequests(specs: List<ModelDownloadSpec>): List<List<ModelDownloadSpec>> {
        val groups = mutableListOf<Set<ModelDownloadSpec>>()
        specs.distinct().forEach { spec ->
            val group = expand(listOf(spec)).toMutableSet()
            val overlapping = groups.filter { existing -> existing.any { it in group } }
            overlapping.forEach { group += it }
            groups.removeAll(overlapping.toSet())
            groups += group
        }
        return groups.map { expand(it.toList()) }
    }
}

internal fun modelReadinessWithDependencies(
    spec: ModelDownloadSpec,
    checkArtifact: (ModelDownloadSpec) -> ModelReadiness,
): ModelReadiness {
    val artifacts = ModelDownloadDependencies.expand(listOf(spec)).map(checkArtifact)
    return ModelReadiness(
        spec = spec,
        installed = artifacts.all { it.installed },
        supported = artifacts.all { it.supported },
        totalBytes = artifacts.sumOf { it.totalBytes },
    )
}
