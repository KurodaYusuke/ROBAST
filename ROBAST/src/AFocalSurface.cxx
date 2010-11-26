// $Id: AFocalSurface.cxx,v 1.2 2008/03/26 05:50:47 oxon Exp $
// Author: Akira Okumura 2007/10/01

/******************************************************************************
 * Copyright (C) 2006-, Akira Okumura                                         *
 * All rights reserved.                                                       *
 *****************************************************************************/

///////////////////////////////////////////////////////////////////////////////
//
// AFocalSurface
//
// FocalSurface class
//
///////////////////////////////////////////////////////////////////////////////

#include "AFocalSurface.h"

ClassImp(AFocalSurface)

AFocalSurface::AFocalSurface()
{
  // Default constructor
  SetLineColor(2);
}

//_____________________________________________________________________________
AFocalSurface::AFocalSurface(const char* name, const TGeoShape* shape,
			   const TGeoMedium* med)
  : AOpticalComponent(name, shape, med)
{
  SetLineColor(2);
}

//_____________________________________________________________________________
AFocalSurface::~AFocalSurface()
{
}