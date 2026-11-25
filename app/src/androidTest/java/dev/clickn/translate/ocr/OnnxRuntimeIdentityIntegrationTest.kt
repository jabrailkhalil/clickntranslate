package dev.clickn.translate.ocr

import ai.onnxruntime.OnnxJavaType
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.nio.FloatBuffer
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Actual JNI/session/inference contract, including minified validation APKs; not OCR quality. */
@RunWith(AndroidJUnit4::class)
class OnnxRuntimeIdentityIntegrationTest {
    @Test fun nativeRuntimeRunsOwnedFloatIdentityAndReleasesOnlyItsOwnedResources() {
        val model = InstrumentationRegistry.getInstrumentation().context.assets
            .open("onnx-identity/identity.onnx").use { it.readBytes() }
        // The environment is shared with production OCR: do not use/close it here.
        val environment = OrtEnvironment.getEnvironment()
        assertEquals("Unexpected native runtime was loaded", "1.21.1", environment.version)
        val expected = floatArrayOf(1f, -2.5f, 0f, 42f)
        val shape = longArrayOf(1L, 4L)
        OrtSession.SessionOptions().use { options ->
            options.setInterOpNumThreads(1)
            options.setIntraOpNumThreads(1)
            environment.createSession(model, options).use { session ->
                assertEquals(setOf("X"), session.inputNames)
                assertEquals(setOf("Y"), session.outputNames)
                val input = OnnxTensor.createTensor(environment, FloatBuffer.wrap(expected), shape)
                input.use { tensor ->
                    var output: OnnxTensor? = null
                    session.run(mapOf("X" to tensor)).use { result ->
                        assertEquals(1, result.size())
                        assertTrue("The result must own its output tensor", result.isResultOwner(0))
                        val value = result.get("Y").orElseThrow { AssertionError("Missing Identity output Y") }
                        assertTrue("Identity returned a non-tensor", value is OnnxTensor)
                        val produced = value as OnnxTensor
                        output = produced
                        assertArrayEquals(shape, produced.info.shape)
                        assertEquals(OnnxJavaType.FLOAT, produced.info.type)
                        val rows = produced.value as Array<*>
                        assertEquals(1, rows.size)
                        assertArrayEquals(expected, rows.single() as FloatArray, 0f)
                        assertFalse(tensor.isClosed)
                        assertFalse(produced.isClosed)
                    }
                    // Result.close owns this output; avoid a second independent output.close.
                    assertTrue("Result.close retained the output", requireNotNull(output).isClosed)
                }
                assertTrue("Input tensor was retained", input.isClosed)
            }
        }
        assertSame("The shared environment was replaced", environment, OrtEnvironment.getEnvironment())
    }
}
