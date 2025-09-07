import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import numpy as np

class CortexVisualizer:
    """
    Visualization component for Cortex AI Services Cost Analyzer.
    Creates interactive charts and graphs for service breakdown and reconciliation analysis.
    """
    
    def __init__(self):
        """Initialize visualizer with consistent styling and color schemes."""
        
        # Color scheme for Cortex services (consistent across all charts)
        self.service_colors = {
            'CORTEX_FUNCTIONS_USAGE': '#1f77b4',      # Blue
            'CORTEX_ANALYST': '#ff7f0e',              # Orange  
            'CORTEX_DOCUMENT_PROCESSING': '#2ca02c',   # Green
            'CORTEX_FUNCTIONS_QUERY': '#d62728',       # Red
            'CORTEX_SEARCH_DAILY': '#9467bd',          # Purple
            'CORTEX_SEARCH_SERVING': '#8c564b'         # Brown
        }
        
        # Status colors for reconciliation
        self.status_colors = {
            'EXCELLENT': '#28a745',    # Green
            'GOOD': '#ffc107',         # Yellow
            'WARNING': '#fd7e14',      # Orange
            'CRITICAL': '#dc3545',     # Red
            'UNKNOWN': '#6c757d'       # Gray
        }
        
        # Common layout styling
        self.common_layout = {
            'font': {'size': 12},
            'showlegend': True,
            'margin': {'l': 40, 'r': 40, 't': 60, 'b': 40},
            'plot_bgcolor': 'rgba(0,0,0,0)',
            'paper_bgcolor': 'rgba(0,0,0,0)'
        }
    
    def create_service_pie_chart(self, service_data: pd.DataFrame) -> go.Figure:
        """
        Create pie chart showing service breakdown by credits.
        
        Args:
            service_data: DataFrame with service breakdown data
            
        Returns:
            Plotly figure object
        """
        if service_data.empty:
            return self._create_empty_chart("No service data available")
        
        # Filter out zero-credit services for cleaner visualization
        active_services = service_data[service_data['total_credits'] > 0].copy()
        
        if active_services.empty:
            return self._create_empty_chart("No active services in selected period")
        
        # Create color mapping
        colors = [self.service_colors.get(service, '#95a5a6') 
                 for service in active_services['service_type']]
        
        fig = go.Figure(data=[go.Pie(
            labels=active_services['service_type'],
            values=active_services['total_credits'],
            hole=0.4,  # Donut chart
            marker=dict(colors=colors, line=dict(color='#FFFFFF', width=2)),
            textinfo='label+percent',
            textposition='outside',
            hovertemplate='<b>%{label}</b><br>' +
                         'Credits: %{value:.6f}<br>' +
                         'Percentage: %{percent}<br>' +
                         '<extra></extra>'
        )])
        
        fig.update_layout(
            title={
                'text': '🔧 Service Breakdown by Credits',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': '#1f2937'}
            },
            **self.common_layout,
            height=400
        )
        
        # Add center text with total
        total_credits = active_services['total_credits'].sum()
        fig.add_annotation(
            text=f"Total<br>{total_credits:.3f}<br>Credits",
            x=0.5, y=0.5,
            font_size=14,
            showarrow=False
        )
        
        return fig
    
    def create_service_bar_chart(self, service_data: pd.DataFrame) -> go.Figure:
        """
        Create horizontal bar chart showing service credits and record counts.
        
        Args:
            service_data: DataFrame with service breakdown data
            
        Returns:
            Plotly figure object with dual y-axis
        """
        if service_data.empty:
            return self._create_empty_chart("No service data available")
        
        # Sort by total credits for better visualization
        sorted_data = service_data.sort_values('total_credits', ascending=True)
        
        # Create subplot with secondary y-axis
        fig = make_subplots(
            rows=1, cols=1,
            specs=[[{"secondary_y": True}]]
        )
        
        # Credits bar chart
        colors = [self.service_colors.get(service, '#95a5a6') 
                 for service in sorted_data['service_type']]
        
        fig.add_trace(
            go.Bar(
                y=sorted_data['service_type'],
                x=sorted_data['total_credits'],
                orientation='h',
                name='Credits',
                marker_color=colors,
                text=sorted_data['total_credits'].apply(lambda x: f"{x:.3f}"),
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>' +
                             'Credits: %{x:.6f}<br>' +
                             '<extra></extra>'
            ),
            secondary_y=False
        )
        
        # Record count line
        fig.add_trace(
            go.Scatter(
                x=sorted_data['record_count'],
                y=sorted_data['service_type'],
                mode='markers+lines',
                name='Records',
                line=dict(color='rgba(255,0,0,0.6)', width=2),
                marker=dict(size=8, color='red'),
                hovertemplate='<b>%{y}</b><br>' +
                             'Records: %{x:,}<br>' +
                             '<extra></extra>'
            ),
            secondary_y=True
        )
        
        # Update layout
        fig.update_layout(
            title={
                'text': '📊 Service Usage: Credits vs Records',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': '#1f2937'}
            },
            **self.common_layout,
            height=max(300, len(sorted_data) * 40),
            showlegend=True
        )
        
        # Update x-axis labels
        fig.update_xaxes(title_text="Credits Used", secondary_y=False)
        fig.update_xaxes(title_text="Record Count", secondary_y=True, overlaying='x', side='top')
        
        return fig
    
    def create_reconciliation_variance_chart(self, reconciliation_results: Dict[str, Any]) -> go.Figure:
        """
        Create variance chart showing reconciliation between tiers.
        
        Args:
            reconciliation_results: Results from ReconciliationEngine
            
        Returns:
            Plotly figure showing tier comparison and variances
        """
        try:
            # Extract tier data
            tiers_data = []
            
            if reconciliation_results.get('organization', {}).get('available', False):
                tiers_data.append({
                    'tier': 'Organization',
                    'credits': reconciliation_results['organization']['credits'],
                    'description': 'Billing baseline'
                })
            
            tiers_data.extend([
                {
                    'tier': 'Account Hourly',
                    'credits': reconciliation_results['account_hourly']['credits'],
                    'description': 'Metering baseline'
                },
                {
                    'tier': 'Granular Services',
                    'credits': reconciliation_results['granular_services']['credits'],
                    'description': 'Service sum'
                }
            ])
            
            df = pd.DataFrame(tiers_data)
            
            if df.empty:
                return self._create_empty_chart("No reconciliation data available")
            
            # Create bar chart with variance indicators
            fig = go.Figure()
            
            # Main bars
            fig.add_trace(go.Bar(
                x=df['tier'],
                y=df['credits'],
                name='Credits',
                marker_color=['#1f77b4', '#ff7f0e', '#2ca02c'][:len(df)],
                text=df['credits'].apply(lambda x: f"{x:.6f}"),
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>' +
                             'Credits: %{y:.6f}<br>' +
                             '<extra></extra>'
            ))
            
            # Add variance annotations
            variance_hourly_granular = reconciliation_results.get('variance_hourly_granular')
            if variance_hourly_granular is not None:
                status = reconciliation_results.get('reconciliation_status', 'UNKNOWN')
                color = self.status_colors.get(status, '#6c757d')
                
                fig.add_annotation(
                    x=len(df)-1,
                    y=max(df['credits']) * 1.1,
                    text=f"Variance: {variance_hourly_granular:+.3f}%<br>Status: {status}",
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor=color,
                    bordercolor=color,
                    borderwidth=2,
                    bgcolor="white"
                )
            
            fig.update_layout(
                title={
                    'text': '🔍 Three-Tier Reconciliation',
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16, 'color': '#1f2937'}
                },
                xaxis_title='Reconciliation Tier',
                yaxis_title='Credits',
                **self.common_layout,
                height=400
            )
            
            return fig
            
        except Exception as e:
            return self._create_empty_chart(f"Error creating reconciliation chart: {str(e)}")
    
    def create_time_series_chart(self, time_series_data: pd.DataFrame, 
                                granularity: str = 'daily') -> go.Figure:
        """
        Create time series chart showing usage trends over time.
        
        Args:
            time_series_data: DataFrame with time series data
            granularity: 'daily' or 'hourly'
            
        Returns:
            Plotly figure with time series data
        """
        if time_series_data.empty:
            return self._create_empty_chart("No time series data available")
        
        fig = go.Figure()
        
        # Add line for each service
        for service in time_series_data['service_type'].unique():
            service_data = time_series_data[time_series_data['service_type'] == service]
            
            if not service_data.empty:
                color = self.service_colors.get(service, '#95a5a6')
                
                fig.add_trace(go.Scatter(
                    x=service_data['period'],
                    y=service_data['credits'],
                    mode='lines+markers',
                    name=service,
                    line=dict(color=color, width=2),
                    marker=dict(size=6),
                    hovertemplate='<b>%{fullData.name}</b><br>' +
                                 'Date: %{x}<br>' +
                                 'Credits: %{y:.6f}<br>' +
                                 '<extra></extra>'
                ))
        
        fig.update_layout(
            title={
                'text': f'📈 Usage Trends ({granularity.title()})',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': '#1f2937'}
            },
            xaxis_title='Date',
            yaxis_title='Credits',
            **self.common_layout,
            height=400,
            hovermode='x unified'
        )
        
        return fig
    
    def create_service_coverage_gauge(self, service_coverage: float) -> go.Figure:
        """
        Create gauge chart showing service coverage percentage.
        
        Args:
            service_coverage: Coverage percentage (0-100+)
            
        Returns:
            Plotly gauge figure
        """
        # Determine color based on coverage
        if service_coverage >= 99.5:
            color = '#28a745'  # Green
        elif service_coverage >= 95.0:
            color = '#ffc107'  # Yellow
        elif service_coverage >= 90.0:
            color = '#fd7e14'  # Orange
        else:
            color = '#dc3545'  # Red
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=service_coverage,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Service Coverage %", 'font': {'size': 16}},
            delta={'reference': 100.0, 'valueformat': '.2f'},
            gauge={
                'axis': {'range': [None, 110]},
                'bar': {'color': color},
                'steps': [
                    {'range': [0, 90], 'color': "lightgray"},
                    {'range': [90, 95], 'color': "gray"},
                    {'range': [95, 100], 'color': "lightgreen"},
                    {'range': [100, 110], 'color': "green"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 100
                }
            }
        ))
        
        fig.update_layout(
            height=300,
            margin={'l': 20, 'r': 20, 't': 40, 'b': 20}
        )
        
        return fig
    
    def create_variance_trend_chart(self, variance_data: pd.DataFrame) -> go.Figure:
        """
        Create chart showing variance trends over time.
        
        Args:
            variance_data: DataFrame with variance trend data
            
        Returns:
            Plotly figure showing variance trends
        """
        if variance_data.empty:
            return self._create_empty_chart("No variance trend data available")
        
        fig = go.Figure()
        
        # Variance line
        fig.add_trace(go.Scatter(
            x=variance_data['date'],
            y=variance_data['variance_pct'],
            mode='lines+markers',
            name='Variance %',
            line=dict(color='#1f77b4', width=2),
            marker=dict(size=6),
            hovertemplate='Date: %{x}<br>' +
                         'Variance: %{y:.3f}%<br>' +
                         '<extra></extra>'
        ))
        
        # Add threshold lines
        fig.add_hline(y=1.0, line_dash="dash", line_color="green", 
                     annotation_text="Excellent (1%)")
        fig.add_hline(y=2.0, line_dash="dash", line_color="orange", 
                     annotation_text="Good (2%)")
        fig.add_hline(y=5.0, line_dash="dash", line_color="red", 
                     annotation_text="Warning (5%)")
        
        fig.update_layout(
            title={
                'text': '📊 Variance Trend Analysis',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': '#1f2937'}
            },
            xaxis_title='Date',
            yaxis_title='Variance %',
            **self.common_layout,
            height=400
        )
        
        return fig
    
    def create_service_details_table(self, service_details: pd.DataFrame) -> pd.DataFrame:
        """
        Format service details data for display as table.
        
        Args:
            service_details: Raw service details data
            
        Returns:
            Formatted DataFrame for display
        """
        if service_details.empty:
            return pd.DataFrame({'Message': ['No service details available']})
        
        # Format for display
        display_df = service_details.copy()
        
        # Format numeric columns
        if 'total_credits' in display_df.columns:
            display_df['Credits'] = display_df['total_credits'].apply(
                lambda x: f"{x:.6f}" if pd.notnull(x) else "0.000000"
            )
        
        if 'percentage' in display_df.columns:
            display_df['Share %'] = display_df['percentage'].apply(
                lambda x: f"{x:.2f}%" if pd.notnull(x) else "0.00%"
            )
        
        if 'record_count' in display_df.columns:
            display_df['Records'] = display_df['record_count'].apply(
                lambda x: f"{x:,}" if pd.notnull(x) else "0"
            )
        
        # Add status indicators
        if 'status' in display_df.columns:
            status_map = {
                'ACTIVE': '✅ Active',
                'INACTIVE': '⚪ Inactive', 
                'NO_DATA': '❌ No Data',
                'ERROR': '🔴 Error'
            }
            display_df['Status'] = display_df['status'].map(status_map).fillna('❓ Unknown')
        
        # Select and reorder columns for display
        display_columns = ['service_type', 'Credits', 'Share %', 'Records', 'granularity', 'Status']
        available_columns = [col for col in display_columns if col in display_df.columns]
        
        result_df = display_df[available_columns].copy()
        
        # Rename columns for better display
        column_rename = {
            'service_type': 'Service Type',
            'granularity': 'Granularity'
        }
        result_df = result_df.rename(columns=column_rename)
        
        return result_df
    
    def create_executive_summary_metrics(self, summary_data: Dict[str, Any]) -> Dict[str, go.Figure]:
        """
        Create metric cards for executive summary.
        
        Args:
            summary_data: Dictionary with summary metrics
            
        Returns:
            Dictionary of Plotly figures for metrics
        """
        figures = {}
        
        # Total credits metric
        total_credits = summary_data.get('total_credits', 0)
        prev_credits = summary_data.get('previous_period_credits', 0)
        
        if prev_credits > 0:
            change_pct = ((total_credits - prev_credits) / prev_credits) * 100
            delta_text = f"{change_pct:+.1f}%"
            delta_color = "green" if change_pct >= 0 else "red"
        else:
            delta_text = "N/A"
            delta_color = "gray"
        
        figures['total_credits'] = go.Figure(go.Indicator(
            mode="number+delta",
            value=total_credits,
            number={'valueformat': '.3f', 'suffix': ' credits'},
            delta={'reference': prev_credits, 'valueformat': '.1%', 'font': {'color': delta_color}},
            title={'text': "Total AI Services", 'font': {'size': 14}}
        ))
        
        # Reconciliation status
        recon_status = summary_data.get('reconciliation_status', 'UNKNOWN')
        recon_accuracy = summary_data.get('reconciliation_accuracy', 0)
        
        status_color = self.status_colors.get(recon_status, '#6c757d')
        
        figures['reconciliation'] = go.Figure(go.Indicator(
            mode="number",
            value=recon_accuracy,
            number={'valueformat': '.2f', 'suffix': '%', 'font': {'color': status_color}},
            title={'text': f"Reconciliation ({recon_status})", 'font': {'size': 14}}
        ))
        
        # Update layout for all metric figures
        for fig in figures.values():
            fig.update_layout(
                height=150,
                margin={'l': 20, 'r': 20, 't': 40, 'b': 20},
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
        
        return figures
    
    def _create_empty_chart(self, message: str) -> go.Figure:
        """
        Create empty chart with message for error/no data states.
        
        Args:
            message: Message to display
            
        Returns:
            Empty Plotly figure with message
        """
        fig = go.Figure()
        
        fig.add_annotation(
            x=0.5, y=0.5,
            text=message,
            showarrow=False,
            font=dict(size=16, color="gray"),
            xref="paper", yref="paper"
        )
        
        fig.update_layout(
            **self.common_layout,
            height=300,
            xaxis={'visible': False},
            yaxis={'visible': False}
        )
        
        return fig
    
    def get_color_for_service(self, service_name: str) -> str:
        """
        Get consistent color for a service across all visualizations.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Hex color code
        """
        return self.service_colors.get(service_name, '#95a5a6')
    
    def get_color_for_status(self, status: str) -> str:
        """
        Get color for reconciliation status.
        
        Args:
            status: Reconciliation status
            
        Returns:
            Hex color code
        """
        return self.status_colors.get(status, '#6c757d')
    
    def create_custom_chart(self, chart_type: str, data: pd.DataFrame, 
                           config: Dict[str, Any]) -> go.Figure:
        """
        Create custom chart based on configuration.
        
        Args:
            chart_type: Type of chart ('bar', 'line', 'pie', 'scatter')
            data: DataFrame with chart data
            config: Chart configuration dictionary
            
        Returns:
            Plotly figure object
        """
        if data.empty:
            return self._create_empty_chart("No data available for custom chart")
        
        try:
            if chart_type == 'bar':
                fig = px.bar(
                    data, 
                    x=config.get('x_column'),
                    y=config.get('y_column'),
                    color=config.get('color_column'),
                    title=config.get('title', 'Custom Bar Chart')
                )
            elif chart_type == 'line':
                fig = px.line(
                    data,
                    x=config.get('x_column'),
                    y=config.get('y_column'),
                    color=config.get('color_column'),
                    title=config.get('title', 'Custom Line Chart')
                )
            elif chart_type == 'pie':
                fig = px.pie(
                    data,
                    values=config.get('values_column'),
                    names=config.get('names_column'),
                    title=config.get('title', 'Custom Pie Chart')
                )
            elif chart_type == 'scatter':
                fig = px.scatter(
                    data,
                    x=config.get('x_column'),
                    y=config.get('y_column'),
                    color=config.get('color_column'),
                    size=config.get('size_column'),
                    title=config.get('title', 'Custom Scatter Chart')
                )
            else:
                return self._create_empty_chart(f"Unsupported chart type: {chart_type}")
            
            # Apply common layout
            fig.update_layout(**self.common_layout)
            
            return fig
            
        except Exception as e:
            return self._create_empty_chart(f"Error creating {chart_type} chart: {str(e)}")
