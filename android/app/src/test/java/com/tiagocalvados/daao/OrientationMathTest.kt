package com.tiagocalvados.daao

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class OrientationMathTest {
    @Test
    fun rearCameraFacingNorthIsZeroDegrees() {
        val pose = OrientationMath.cameraPose(
            floatArrayOf(
                1f, 0f, 0f,
                0f, 0f, -1f,
                0f, 1f, 0f,
            ),
        )

        assertEquals(0.0, pose.magneticBearingDegrees!!, 0.0001)
        assertEquals(0.0, pose.elevationDegrees, 0.0001)
        assertEquals(0.0, pose.cameraRollDegrees!!, 0.0001)
    }

    @Test
    fun rearCameraFacingEastIsNinetyDegrees() {
        val pose = OrientationMath.cameraPose(
            floatArrayOf(
                0f, 0f, -1f,
                -1f, 0f, 0f,
                0f, 1f, 0f,
            ),
        )

        assertEquals(90.0, pose.magneticBearingDegrees!!, 0.0001)
        assertEquals(0.0, pose.elevationDegrees, 0.0001)
    }

    @Test
    fun rearCameraPointingDownHasNoDefinedBearing() {
        val pose = OrientationMath.cameraPose(
            floatArrayOf(
                1f, 0f, 0f,
                0f, 1f, 0f,
                0f, 0f, 1f,
            ),
        )

        assertNull(pose.magneticBearingDegrees)
        assertEquals(-90.0, pose.elevationDegrees, 0.0001)
        assertEquals(0.0, pose.deviceTopBearingDegrees!!, 0.0001)
        assertNull(pose.cameraRollDegrees)
    }

    @Test
    fun cameraRollMeasuresHorizonRotation() {
        val cosine = 0.8660254f
        val sine = 0.5f
        val pose = OrientationMath.cameraPose(
            floatArrayOf(
                cosine, -sine, 0f,
                0f, 0f, -1f,
                sine, cosine, 0f,
            ),
        )

        assertEquals(0.0, pose.elevationDegrees, 0.0001)
        assertEquals(30.0, pose.cameraRollDegrees!!, 0.0001)
    }

    @Test
    fun cameraRollTracksTheRotatedOutputFrame() {
        assertEquals(0.0, OrientationMath.cameraRollForTarget(90.0, 90)!!, 0.0001)
        assertEquals(0.0, OrientationMath.cameraRollForTarget(-90.0, 270)!!, 0.0001)
        assertEquals(-170.0, OrientationMath.cameraRollForTarget(10.0, 180)!!, 0.0001)
        assertNull(OrientationMath.cameraRollForTarget(null, 90))
    }
}
