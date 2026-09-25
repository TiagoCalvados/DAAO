package com.tiagocalvados.daao

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SkyGuideTest {
    @Test
    fun pointedQuestionUsesObjectNearCameraCenter() {
        val sky = listOf(
            SkyObject("Moon", 30.0, 110.0, -12.0),
            SkyObject("Vega", 45.0, 190.0, 0.03),
        )
        val answer = SkyGuide.answer("What is that bright star in front of me?", sky, 30.0, 110.0)
        assertTrue(answer.contains("Moon"))
        assertTrue(!answer.contains("Vega"))
    }

    @Test
    fun descriptionOnlyListsObjectsInCameraDirection() {
        val sky = listOf(
            SkyObject("Moon", 31.0, 111.0, -12.0),
            SkyObject("Vega", 45.0, 190.0, 0.03),
        )
        val answer = SkyGuide.answer("Please describe what you see now", sky, 30.0, 110.0)
        assertTrue(answer.contains("Moon"))
        assertTrue(!answer.contains("Vega"))
    }

    @Test
    fun marsGuidanceAndBelowHorizonAreGrounded() {
        val mars = SkyObject("Mars", 35.0, 120.0, -1.5)
        assertTrue(SkyGuide.answer("Where can I find Mars?", listOf(mars), 20.0, 90.0).contains("right"))
        assertTrue(SkyGuide.answer("Where can I find Mars?", emptyList(), 20.0, 90.0).contains("below the horizon"))
    }

    @Test
    fun missingSensorsDoNotProduceAnIdentification() {
        assertTrue(SkyGuide.answer("What is that?", null, null, null).contains("need your location"))
        assertEquals(90.0, SkyGuide.separation(0.0, 0.0, 0.0, 90.0), 0.0001)
    }
}
