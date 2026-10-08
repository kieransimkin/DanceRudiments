from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import copy
import os


class DanceRudimentsConan(ConanFile):
    name = "dancerudiments"
    package_type = "static-library"
    url = "https://github.com/kieransimkin/DanceRudiments"
    license = "MIT AND BSD-3-Clause AND CC0-1.0 AND CC-BY-4.0"
    author = "Kieran Simkin — https://kieransimkin.co.uk/my-songs/"
    homepage = "https://kieransimkin.co.uk/my-songs/"
    description = "Deterministic rhythmic position functions for DanceFlow. Music: https://kieransimkin.co.uk/my-songs/"
    settings = "os", "compiler", "build_type", "arch"
    exports_sources = "CMakeLists.txt", "cmake/**", "include/**", "src/**", "LICENSE", "collections/initial/THIRD_PARTY_NOTICES.md", "collections/initial/sources/d3-ease/LICENSE", "README.md", "AUTHORS.md", "docs/**", "examples/bindings/**"

    def layout(self):
        cmake_layout(self)

    def generate(self):
        toolchain = CMakeToolchain(self)
        toolchain.variables["DANCERUDIMENTS_BUILD_TESTS"] = False
        toolchain.variables["DANCERUDIMENTS_BUILD_PYTHON"] = False
        toolchain.variables["DANCERUDIMENTS_BUILD_WASM"] = False
        toolchain.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        for filename in ("README.md", "AUTHORS.md"):
            copy(self, filename, src=self.source_folder, dst=self.package_folder)
        copy(self, "*", src=os.path.join(self.source_folder, "docs"),
             dst=os.path.join(self.package_folder, "docs"))
        copy(self, "*", src=os.path.join(self.source_folder, "examples", "bindings"),
             dst=os.path.join(self.package_folder, "examples", "bindings"),
             excludes=("*/dist/*", "*/bin/*", "*/obj/*", "*/__pycache__/*"))
        copy(self, "LICENSE", src=self.source_folder,
             dst=os.path.join(self.package_folder, "licenses"), keep_path=True)
        copy(self, "THIRD_PARTY_NOTICES.md", src=os.path.join(self.source_folder, "collections", "initial"),
             dst=os.path.join(self.package_folder, "licenses"))
        copy(self, "*.hpp", src=os.path.join(self.source_folder, "include"),
             dst=os.path.join(self.package_folder, "include"))
        copy(self, "*.inc", src=os.path.join(self.source_folder, "include"),
             dst=os.path.join(self.package_folder, "include"))
        copy(self, "*.lib", src=self.build_folder,
             dst=os.path.join(self.package_folder, "lib"), keep_path=False)
        copy(self, "*.a", src=self.build_folder,
             dst=os.path.join(self.package_folder, "lib"), keep_path=False)

    def package_info(self):
        self.cpp_info.libs = [
            "DanceRudimentsCore" if str(self.settings.os) == "Windows"
            else "DanceRudiments"
        ]
