/* DanceRudiments C ABI v1. MIT. Kieran Simkin: https://kieransimkin.co.uk/my-songs/
 * Optional bridge for .NET and other FFI clients. No STL or C++ exceptions cross
 * this boundary. Caller-owned buffers must be valid for their declared lengths.
 */
#ifndef DANCERUDIMENTS_C_API_H
#define DANCERUDIMENTS_C_API_H
#include <stdint.h>
#if defined(_WIN32)
# define DR_CALL __cdecl
# if defined(DANCERUDIMENTS_C_EXPORTS)
#  define DR_API __declspec(dllexport)
# else
#  define DR_API __declspec(dllimport)
# endif
#else
# define DR_CALL
# define DR_API __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
# define DR_NOEXCEPT noexcept
extern "C" {
#else
# define DR_NOEXCEPT
#endif

typedef int32_t dr_status;
enum { DR_OK = 0, DR_INVALID_ARGUMENT = 1, DR_OUT_OF_RANGE = 2,
       DR_OUT_OF_MEMORY = 3, DR_INTERNAL_ERROR = 4 };
typedef struct dr_offset3 { double x, y, z; } dr_offset3;
typedef struct dr_info {
  const char* name;                 /* Borrowed, NUL-terminated UTF-8. */
  const char* description;
  uint32_t period_pips;
  uint32_t dimensions;
} dr_info;
typedef struct dr_pattern_definition {
  const char* name;
  const char* description;
  const dr_offset3* samples;
  uint32_t count;
} dr_pattern_definition;
typedef struct dr_library dr_library;

DR_API uint32_t DR_CALL dr_abi_version(void) DR_NOEXCEPT;
DR_API uint32_t DR_CALL dr_pips_per_beat(void) DR_NOEXCEPT;
DR_API const char* DR_CALL dr_version(void) DR_NOEXCEPT;
/* Thread-local error, valid until the next status-returning call on this thread.
 * Does not allocate; diagnostic messages may be truncated. Never free this pointer. */
DR_API const char* DR_CALL dr_last_error(void) DR_NOEXCEPT;
DR_API dr_status DR_CALL dr_catalogue_count(uint32_t* count) DR_NOEXCEPT;
/* Default metadata strings live until the shared library is unloaded. */
DR_API dr_status DR_CALL dr_catalogue_get(uint32_t index, dr_info* info) DR_NOEXCEPT;
DR_API dr_status DR_CALL dr_sample(const char* name, int32_t pip, dr_offset3* value) DR_NOEXCEPT;
/* Maximum 1,048,576 outputs. start + i*step uses int64, then wraps to the
 * movement's period, so int32 endpoints/steps never overflow during a batch.
 * count=0 permits a NULL output but still validates the name. */
DR_API dr_status DR_CALL dr_sample_many(const char* name, int32_t start, int32_t step,
                                      uint32_t count, dr_offset3* values) DR_NOEXCEPT;
/* Copies all input data. An empty bank exposes the defaults. Output is NULL on
 * failure. Limits/duplicate names/default-replacement rules are those of C++.
 * No mutation is exposed; parallel sampling is safe while the handle is alive. */
DR_API dr_status DR_CALL dr_library_create(const dr_pattern_definition* definitions,
                                         uint32_t count, dr_library** result) DR_NOEXCEPT;
DR_API void DR_CALL dr_library_destroy(dr_library* library) DR_NOEXCEPT;
DR_API dr_status DR_CALL dr_library_count(const dr_library* library, uint32_t* count) DR_NOEXCEPT;
/* Copy these strings BEFORE destroying the library. */
DR_API dr_status DR_CALL dr_library_get(const dr_library* library, uint32_t index,
                                      dr_info* info) DR_NOEXCEPT;
DR_API dr_status DR_CALL dr_library_sample(const dr_library* library, const char* name,
                                         int32_t pip, dr_offset3* value) DR_NOEXCEPT;
DR_API dr_status DR_CALL dr_library_sample_many(const dr_library* library, const char* name,
                                              int32_t start, int32_t step, uint32_t count,
                                              dr_offset3* values) DR_NOEXCEPT;
#ifdef __cplusplus
}
#endif
#endif
