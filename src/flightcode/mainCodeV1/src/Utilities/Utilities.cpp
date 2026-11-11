#include "Utilities.h"
#include <cmath>

float Utilities::degToRad(float deg){
    return(deg*M_PI/180.0f);
}

bool Utilities::isSimpleBouded(float u, float u_max)
{
    return (fabsf(u) <= u_max);
}
float Utilities::clamping(float u, float u_max){
    return constrain(u,-u_max,u_max); // 1D constraining
}


float Utilities::EWA(float alpha, float u, float measurement){
    return alpha * measurement + (1-alpha)*u;
}


float Utilities::distance1D(float u, float u_ref){
    return(fabsf(u-u_ref));
}

float Utilities::distance2D(float x, float y, float x_ref, float y_ref){
    float dx = (x-x_ref);
    float dy = (y-y_ref);
    return(sqrtf(dx*dx + dy*dy));
}


float Utilities::distance3D(float x, float y, float z, float x_ref, float y_ref, float z_ref){ 
    float dx = (x-x_ref);
    float dy = (y-y_ref);
    float dz = (z-z_ref);
    return(sqrtf(dx*dx + dy*dy + dz*dz));
}

float Utilities::distance3D(const Vector3& p, const Vector3& p_ref){
    return(distance3D(p.x,p.y,p.z, p_ref.x, p_ref.y , p_ref.z));
}




