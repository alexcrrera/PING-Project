#include <cmath>
#include <cassert>
using namespace std;
struct Gimbal { float pan_deg=0, tilt_deg=0; bool projectRangeNed(float,float,float,float,float&,float&) const; };
bool Gimbal::projectRangeNed(float range_m, float yaw_deg, float pitch_deg, float roll_deg,
                             float& north_m, float& east_m) const
{
    if (!isfinite(range_m) || range_m <= 0 || !isfinite(yaw_deg) ||
        !isfinite(pitch_deg) || !isfinite(roll_deg)) return false;
    const float k = 0.017453292519943295f;
    const float yaw = yaw_deg*k, pitch = pitch_deg*k, roll = roll_deg*k;
    const float pan = pan_deg*k, tilt = tilt_deg*k;
    const float x = cosf(tilt)*cosf(pan), y = cosf(tilt)*sinf(pan), z = -sinf(tilt);
    const float cy=cosf(yaw), sy=sinf(yaw), cp=cosf(pitch), sp=sinf(pitch), cr=cosf(roll), sr=sinf(roll);
    north_m = range_m*(cp*cy*x + (sr*sp*cy-cr*sy)*y + (cr*sp*cy+sr*sy)*z);
    east_m = range_m*(cp*sy*x + (sr*sp*sy+cr*cy)*y + (cr*sp*sy-sr*cy)*z);
    return isfinite(north_m) && isfinite(east_m);
}

int main() { Gimbal g; float n,e; assert(g.projectRangeNed(10,0,0,0,n,e)); assert(fabs(n-10)<0.001 && fabs(e)<0.001); assert(g.projectRangeNed(10,90,0,0,n,e)); assert(fabs(n)<0.001 && fabs(e-10)<0.001); g.pan_deg=90; assert(g.projectRangeNed(10,0,0,0,n,e)); assert(fabs(n)<0.001 && fabs(e-10)<0.001); g.pan_deg=0; g.tilt_deg=60; assert(g.projectRangeNed(10,0,0,0,n,e)); assert(fabs(n-5)<0.001); assert(!g.projectRangeNed(0,0,0,0,n,e)); }
