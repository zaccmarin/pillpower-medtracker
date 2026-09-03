from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime, timedelta
from ..models import MedicationLog


#Mar chart generator funtion using reportlab library to create a PDF document.
#This function takes a resident and a start date as input
#and generates a MAR chart for the resident from the start date to the end of the month

#The document is structured with a header containing resident information and a table for each medication schedule
#The tables show the administration times and the initials of the staff who administered the medication

class MARGenerator:
    def __init__(self, resident, start_date):
        self.resident = resident
        self.start_date = start_date
        self.styles = getSampleStyleSheet()
        
        self.styles.add(ParagraphStyle(
            'Wrapped',
            parent=self.styles['Normal'],
            wordWrap='CJK'
        ))
      
    def generate_mar_chart(self, output_path):
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        
        elements = []
        elements.extend(self._create_header())
        elements.extend(self._create_medication_tables())
        
        doc.build(elements)
    
    def _create_header(self):
        
        conditions = Paragraph(
            self.resident.conditions or 'None known', 
            self.styles['Wrapped']
        )
        allergies = Paragraph(
            self.resident.allergies or 'None known', 
            self.styles['Wrapped']
        )
        
        # Create header table with resident information
        header_data = [
            ['Name:', self.resident.name, 'DOB:', self.resident.date_of_birth.strftime('%d/%m/%Y') if self.resident.date_of_birth else ''],
            ['Room:', self.resident.room_number or 'Not assigned', 'Care Home:', self.resident.carehome.name],
            ['Group:', self.resident.group.name if self.resident.group else 'Not assigned', 'Start Date:', self.start_date.strftime('%d/%m/%Y')],
            ['Allergies:', allergies, '', ''],
            ['Conditions:', conditions, '', '']
        ]
        
        header_table = Table(header_data, colWidths=[1.2*inch, 2.8*inch, 1.2*inch, 2.2*inch])
        header_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
            ('SPAN', (1, 3), (-1, 3)),  
            ('SPAN', (1, 4), (-1, 4)),  
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), 
        ]))
        
        return [header_table, Paragraph("<br/><br/>", self.styles['Normal'])]
    
    def _create_medication_tables(self):
        elements = []
        
        # Get all medications for the resident
        medications = self.resident.medicationschedule_set.all()
        
        for medication in medications:
            elements.extend(self._create_single_medication_table(medication))
            elements.append(Paragraph("<br/><br/>", self.styles['Normal']))
            
        return elements
    
    def _create_single_medication_table(self, medication_schedule):
        
        med_header = [
            [Paragraph(f"<b>Medication:</b> {medication_schedule.medication.name}", self.styles['Normal'])],
            [Paragraph(
                f"<b>Dosage:</b> {medication_schedule.dosage} | "
                f"<b>Route:</b> {medication_schedule.get_route_display()} | "
                f"<b>Frequency:</b> {medication_schedule.frequency} times daily", 
                self.styles['Normal']
            )]
        ]
        
        
        med_table = Table(med_header, colWidths=[7*inch])
        med_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ]))
        
        # Create full month administration table
        dates = [(self.start_date + timedelta(days=x)) for x in range(31)]
        admin_times = medication_schedule.times.all()
        
        elements = [med_table, Paragraph("<br/>", self.styles['Normal'])]
        
        # Split dates into weeks
        weeks = [dates[i:i + 7] for i in range(0, len(dates), 7)]
        
        # Create a table for each week
        for week_dates in weeks:

            # Create the table header with dates
            table_data = [['Time'] + [d.strftime('%d/%m') for d in week_dates]]
            
            # For each administration time
            for time_slot in admin_times:
                row = [time_slot.time.strftime('%H:%M')]
                
                # For each date in the week
                for date in week_dates:

                    # Check if medication was given
                    given = MedicationLog.objects.filter(
                        schedule=medication_schedule,
                        scheduled_time=time_slot,
                        given_at__date=date
                    ).first()
                    
                    if given:
                        # This gets the initals for the Nurse/Carer who gave the medication.
                        initials = f"{given.given_by.user.first_name[0]}{given.given_by.user.last_name[0]}".upper()
                        row.append(initials)
                    else:
                        row.append('')
                    
                table_data.append(row)
            
            # Creates the weekly table
            admin_table = Table(table_data, colWidths=[1*inch] + [0.8*inch]*len(week_dates))
            admin_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            
            elements.append(admin_table)
            elements.append(Paragraph("<br/>", self.styles['Normal']))
        
        return elements