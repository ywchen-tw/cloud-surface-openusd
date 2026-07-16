#include <cmath>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

#include <openvdb/openvdb.h>

namespace {

struct Lobe {
    openvdb::Vec3d center;
    openvdb::Vec3d radius;
    double strength;
};

double ellipsoidDensity(const openvdb::Vec3d& p, const Lobe& lobe)
{
    const double dx = (p.x() - lobe.center.x()) / lobe.radius.x();
    const double dy = (p.y() - lobe.center.y()) / lobe.radius.y();
    const double dz = (p.z() - lobe.center.z()) / lobe.radius.z();
    const double r2 = dx * dx + dy * dy + dz * dz;
    if (r2 >= 1.0) {
        return 0.0;
    }

    const double softFalloff = std::pow(1.0 - r2, 2.2);
    const double verticalCore = std::exp(-0.35 * std::abs(dz));
    return lobe.strength * softFalloff * verticalCore;
}

double fractalRipple(const openvdb::Vec3d& p)
{
    const double a = std::sin(p.x() * 1.4 + p.y() * 0.7);
    const double b = std::sin(p.y() * 1.9 - p.z() * 1.2);
    const double c = std::sin((p.x() + p.y() + p.z()) * 2.7);
    return 0.78 + 0.22 * ((a + b + c) / 3.0);
}

} // namespace

int main(int argc, char** argv)
{
    const std::string outPath = argc > 1 ? argv[1] : "assets/week7/vdbs/cloud_density.vdb";
    const double voxelSize = argc > 2 ? std::stod(argv[2]) : 0.20;

    openvdb::initialize();

    auto grid = openvdb::FloatGrid::create(0.0f);
    grid->setName("density");
    grid->setGridClass(openvdb::GRID_FOG_VOLUME);
    grid->setTransform(openvdb::math::Transform::createLinearTransform(voxelSize));
    grid->insertMeta("description", openvdb::StringMetadata("Week 7 synthetic Arctic cloud density"));

    const std::vector<Lobe> lobes = {
        {{-4.7, -1.1, 0.7}, {5.6, 3.3, 2.0}, 0.62},
        {{-1.4, 0.7, 1.2}, {6.5, 3.8, 2.6}, 0.86},
        {{2.8, -0.6, 1.5}, {5.2, 3.2, 2.7}, 0.80},
        {{5.6, 1.0, 1.1}, {3.7, 2.4, 2.0}, 0.54},
        {{0.6, -2.4, 0.0}, {8.4, 2.4, 1.1}, 0.34},
        {{-0.7, 2.8, 2.6}, {4.8, 2.1, 1.5}, 0.32},
    };

    auto accessor = grid->getAccessor();
    const int minX = static_cast<int>(std::floor(-10.0 / voxelSize));
    const int maxX = static_cast<int>(std::ceil(10.0 / voxelSize));
    const int minY = static_cast<int>(std::floor(-6.0 / voxelSize));
    const int maxY = static_cast<int>(std::ceil(6.0 / voxelSize));
    const int minZ = static_cast<int>(std::floor(-3.0 / voxelSize));
    const int maxZ = static_cast<int>(std::ceil(5.0 / voxelSize));

    std::size_t activeVoxels = 0;
    for (int z = minZ; z <= maxZ; ++z) {
        for (int y = minY; y <= maxY; ++y) {
            for (int x = minX; x <= maxX; ++x) {
                const openvdb::Vec3d p = grid->transform().indexToWorld(openvdb::Vec3d(x + 0.5, y + 0.5, z + 0.5));
                double density = 0.0;
                for (const Lobe& lobe : lobes) {
                    density += ellipsoidDensity(p, lobe);
                }

                const double baseClip = p.z() < -1.7 ? 0.35 * (-1.7 - p.z()) : 0.0;
                density = std::max(0.0, density - baseClip);
                density *= fractalRipple(p);
                density = std::min(density, 1.0);

                if (density > 0.012) {
                    accessor.setValue(openvdb::Coord(x, y, z), static_cast<float>(density));
                    ++activeVoxels;
                }
            }
        }
    }

    grid->tree().prune();
    std::filesystem::create_directories(std::filesystem::path(outPath).parent_path());

    openvdb::io::File file(outPath);
    openvdb::GridPtrVec grids;
    grids.push_back(grid);
    file.write(grids);
    file.close();

    std::cout << "Saved " << outPath << "\n";
    std::cout << "Grid: density, class: fog volume, active voxels: " << activeVoxels << "\n";
    return 0;
}
