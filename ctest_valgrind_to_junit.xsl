<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="xml" indent="yes"/>

  <xsl:template match="/Site">
      <testsuite name="ValgrindTests">
	<properties>
	  <xsl:for-each select="@*">
	    <property>
	      <xsl:attribute name="name">
		<xsl:value-of select="name(.)"/>
	      </xsl:attribute>
	      <xsl:attribute name="value">
		<xsl:value-of select="."/>
	      </xsl:attribute>
	    </property>
	  </xsl:for-each>
	</properties>
	<xsl:apply-templates select="DynamicAnalysis/Test"/>
	<system-out>
	  <xsl:for-each select="@*">
	    <xsl:value-of select="name(.)"/>
	    <xsl:text>: </xsl:text>
	    <xsl:value-of select="."/>
	    <xsl:text>&#10;</xsl:text>
	  </xsl:for-each>
	</system-out>
      </testsuite>
  </xsl:template>
  <xsl:template match="DynamicAnalysis/Test">
    <testcase name="{Name}" classname="ValgrindTests">
      <error>
	<xsl:attribute name="message">
	  <xsl:for-each select="Results/*">
	    <xsl:value-of select="."/>
	    <xsl:text> </xsl:text>
	    <xsl:value-of select="@type"/>
	    <xsl:if test="not(position() = last())">, </xsl:if>
	  </xsl:for-each>
	</xsl:attribute>
	<xsl:value-of select="Log" />
       </error>
    </testcase>
  </xsl:template>
</xsl:stylesheet>
