#include <jni.h>
#include <gguf.h>
#include <cstdio>
#include <cstdint>
#include <exception>
#include <memory>
#include <sys/stat.h>
#include <unistd.h>

extern "C" JNIEXPORT jboolean JNICALL
Java_dev_clickn_translate_llm_GgufTensorRanges_completeNative(JNIEnv *env, jobject, jstring path) {
    if (path == nullptr) return JNI_FALSE;
    const char *name = env->GetStringUTFChars(path, nullptr);
    if (name == nullptr) return JNI_FALSE;
    std::unique_ptr<FILE, decltype(&std::fclose)> file(std::fopen(name, "rb"), &std::fclose);
    env->ReleaseStringUTFChars(path, name);
    struct stat info{};
    if (!file || fstat(fileno(file.get()), &info) != 0 || info.st_size <= 0) return JNI_FALSE;

    try {
        // A null ggml context reads the metadata and tensor index without allocating weights.
        const gguf_init_params params{true, nullptr};
        std::unique_ptr<gguf_context, decltype(&gguf_free)> index(
                gguf_init_from_file_ptr(file.get(), params), &gguf_free);
        if (!index) return JNI_FALSE;
        const auto file_bytes = static_cast<uint64_t>(info.st_size);
        const auto data_start = gguf_get_data_offset(index.get());
        const auto count = gguf_get_n_tensors(index.get());
        if (data_start > file_bytes || count <= 0) return JNI_FALSE;
        const auto available = file_bytes - data_start;
        for (int64_t i = 0; i < count; ++i) {
            const auto offset = gguf_get_tensor_offset(index.get(), i);
            if (offset > available || gguf_get_tensor_size(index.get(), i) > available - offset) {
                return JNI_FALSE;
            }
        }
        return JNI_TRUE;
    } catch (const std::exception &) {
        return JNI_FALSE;
    }
}
