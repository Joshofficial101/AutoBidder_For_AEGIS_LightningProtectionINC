"""
PDF Submittal Generator

Creates professional PDF submittal packages that include:
- Cover sheet with project info
- Compliance certifications (UL 96A, NFPA 780)
- Material list
- Technical specifications

This is what gets sent to the client along with the bid.
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from src.models.bid import Bid
from datetime import date


class PDFSubmittalExporter:
    """
    Generates PDF submittal packages for lightning protection bids.

    Creates a multi-page PDF with cover sheet, compliance info, and material list.
    """

    def __init__(self, contractor_name: str = "Lightning Protection Contractor",
                 contractor_info: dict = None):
        """
        Initialize PDF exporter.

        Args:
            contractor_name: Name of your company
            contractor_info: Dict with address, phone, email, license, etc.
        """
        self.contractor_name = contractor_name
        self.contractor_info = contractor_info or {}

        # Setup styles
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        """Create custom paragraph styles for the PDF."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            spaceBefore=12
        ))

        # Body style
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6
        ))

    def export_submittal(self, bid: Bid, output_path: Path, compliance_code: str = "UL 96A") -> Path:
        """
        Generate complete PDF submittal package.

        Args:
            bid: The Bid object
            output_path: Where to save PDF
            compliance_code: Which compliance standard ('UL 96A' or 'NFPA 780')

        Returns:
            Path to created PDF
        """
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch
        )

        # Build document content
        story = []

        # Page 1: Cover sheet
        story.extend(self._create_cover_page(bid, compliance_code))
        story.append(PageBreak())

        # Page 2: Compliance certification
        story.extend(self._create_compliance_page(bid, compliance_code))
        story.append(PageBreak())

        # Page 3: Material list
        story.extend(self._create_material_list_page(bid))

        # Build PDF
        doc.build(story)
        return output_path

    def _create_cover_page(self, bid: Bid, compliance_code: str):
        """Create the cover page of the submittal."""
        content = []

        # Title
        title = Paragraph(
            "Lightning Protection System<br/>Submittal Package",
            self.styles['CustomTitle']
        )
        content.append(title)
        content.append(Spacer(1, 0.3*inch))

        # Project info box
        project_data = [
            ['Project Name:', bid.project_name],
            ['Date:', date.today().strftime('%B %d, %Y')],
            ['Compliance Standard:', compliance_code],
            ['Total Bid Amount:', f"${bid.final_bid_amount:,.2f}"],
        ]

        project_table = Table(project_data, colWidths=[2*inch, 4*inch])
        project_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#d9e1f2')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        content.append(project_table)
        content.append(Spacer(1, 0.5*inch))

        # Contractor info
        content.append(Paragraph("Submitted By:", self.styles['SectionHeader']))

        contractor_data = [
            ['Company:', self.contractor_name],
            ['Address:', self.contractor_info.get('address', 'N/A')],
            ['Phone:', self.contractor_info.get('phone', 'N/A')],
            ['Email:', self.contractor_info.get('email', 'N/A')],
            ['License:', self.contractor_info.get('license', 'N/A')],
        ]

        contractor_table = Table(contractor_data, colWidths=[1.5*inch, 4.5*inch])
        contractor_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))

        content.append(contractor_table)
        content.append(Spacer(1, 0.5*inch))

        # Certification statement
        cert_text = f"""
        This submittal package certifies that the proposed lightning protection system
        complies with <b>{compliance_code}</b> standards. All materials and installation
        methods meet or exceed the requirements of the applicable codes and standards.
        """
        content.append(Paragraph(cert_text, self.styles['CustomBody']))

        return content

    def _create_compliance_page(self, bid: Bid, compliance_code: str):
        """Create the compliance certification page."""
        content = []

        content.append(Paragraph(f"{compliance_code} Compliance Certification", self.styles['CustomTitle']))
        content.append(Spacer(1, 0.2*inch))

        # Compliance sections
        if compliance_code == "UL 96A":
            sections = [
                ("Air Terminals", "Air terminals installed per UL 96A Section 4.1. Maximum 20 ft spacing on roof perimeter and edges. Minimum height 10 inches above protected surface."),
                ("Conductors", "Main conductors and down conductors per UL 96A Section 4.2. Minimum two-way path to ground. 8-inch minimum bending radius maintained throughout."),
                ("Grounding", "Ground electrodes per UL 96A Section 4.3. Minimum 10 ft depth. Ground resistance tested to verify <25 ohms."),
                ("Bonding", "All metal bodies within 6 ft of system bonded per UL 96A Section 4.4."),
            ]
        else:  # NFPA 780
            sections = [
                ("Air Terminals", "Air terminals installed per NFPA 780 Chapter 4. Maximum 25 ft spacing. Strike termination devices positioned to intercept lightning strikes."),
                ("Conductors", "Main and down conductors per NFPA 780 Chapter 4. Two-way path to ground minimum. Proper bonding at all interconnections."),
                ("Grounding", "Grounding electrodes per NFPA 780 Chapter 4. Ground ring system recommended for optimal performance."),
                ("Bonding", "Comprehensive bonding of all metal objects per NFPA 780 Chapter 4. Metal roof bonding included where applicable."),
            ]

        for section_name, section_text in sections:
            content.append(Paragraph(section_name, self.styles['SectionHeader']))
            content.append(Paragraph(section_text, self.styles['CustomBody']))
            content.append(Spacer(1, 0.15*inch))

        # Materials certification
        content.append(Spacer(1, 0.3*inch))
        content.append(Paragraph("Materials Certification", self.styles['SectionHeader']))
        materials_text = """
        All materials used in this installation are listed and labeled per the applicable
        standard. Copper and aluminum components meet minimum conductivity requirements.
        All fasteners, connectors, and grounding electrodes are approved for lightning
        protection system use.
        """
        content.append(Paragraph(materials_text, self.styles['CustomBody']))

        return content

    def _create_material_list_page(self, bid: Bid):
        """Create the material list page."""
        content = []

        content.append(Paragraph("Bill of Materials", self.styles['CustomTitle']))
        content.append(Spacer(1, 0.2*inch))

        # Summary by section
        for section in bid.sections:
            content.append(Paragraph(section.name, self.styles['SectionHeader']))

            # Table data
            table_data = [['Item', 'Quantity', 'Unit', 'Description']]

            for item in section.line_items:
                table_data.append([
                    item.price_item.code,
                    f"{item.quantity:.1f}",
                    item.price_item.unit or "ea",
                    item.price_item.name
                ])

            # Create table
            material_table = Table(table_data, colWidths=[1*inch, 1*inch, 0.75*inch, 3.5*inch])
            material_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#366092')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
            ]))

            content.append(material_table)
            content.append(Spacer(1, 0.3*inch))

        return content
