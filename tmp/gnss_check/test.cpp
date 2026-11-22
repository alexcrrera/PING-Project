#include <cassert>
#include <cmath>
#include "VN300_parsing.h"
int main() {
 VN300Measurement m;
 char valid[] = "$VNRRG,58,333733.000159,1694,3,05,+32.95622080,-096.71415970,+00169.457,-000.850,-000.580,-002.860,+005.573,+003.644,+009.760,+003.320,2.00E-08*0E";
 assert(VN300Parsing::parse_GNSS_Solution_LLA(valid,m));
 assert(m.gnssSolution.NumSats == 5 && fabs(m.gnssSolution.Lat-32.95622080)<1e-8);
 assert(fabs(m.gnssSolution.VelN+0.850)<1e-5 && fabs(m.gnssSolution.PosUncertaintyE-3.644)<1e-5);
 assert(fabs(m.gnssSolution.GnssVelUncertainty-3.320)<1e-5 && m.gnssReceivedAtMs==123);
 valid[20] = '9';
 assert(!VN300Parsing::parse_GNSS_Solution_LLA(valid,m));
 assert(fabs(m.gnssSolution.Lat-32.95622080)<1e-8);
}
