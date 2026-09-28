from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import copy
import os


class DanceRudimentsConan(ConanFile):
    name = "dancerudiments"
    package_type = "static-library"
    url = "https://github.com/kieransimkin/DanceRudiments"
    description = "Integer-pip rhythmic position functions"
    settings = "os", "compiler", "build_type", "arch"
    exports_sources = "CMakeLists.txt", "include/**", "src/**"

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
        copy(self, "*.hpp", src=os.path.join(self.source_folder, "include"),
             dst=os.path.join(self.package_folder, "include"))
        copy(self, "*.lib", src=self.build_folder,
             dst=os.path.join(self.package_folder, "lib"), keep_path=False)
        copy(self, "*.a", src=self.build_folder,
             dst=os.path.join(self.package_folder, "lib"), keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["DanceRudiments"]
