from datetime import datetime
from langchain import hub
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.tools.tavily_search import TavilySearchResults

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import os
from langchain_community.document_loaders import WebBaseLoader
from bs4 import BeautifulSoup
import asyncio

load_dotenv()
# Get current year
current_year = datetime.now().year
# Set up the language models for different agents
search_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
filter_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
finalizer_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
# Set up the Tavily search tool
search_tool = TavilySearchResults(
    max_results=10,  # Increased to get more results
    search_depth="advanced",
    include_answer=True,
    include_raw_content=True,
)
# Define the tools
tools = [search_tool]


def find_potential_clients(industry, country, additional_requirements=""):
    # Define prompts for each agent
    search_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"""You are an expert at finding potential consulting clients. Your task is to:
                1. Search for companies in the {industry} industry from {country} that might need consulting services
                2. Consider these specific requirements when searching:
                   {additional_requirements if additional_requirements else "No additional requirements specified"}
                3. Use the search tool to find companies that match these criteria
                4. Generate follow-up searches based on initial findings
                5. Focus on {current_year} data when available
                6. Look for companies that match the size and requirements specified
                7. Gather information about:
                   - Company growth and market position
                   - Current challenges that align with the requirements
                   - Transformation and expansion plans
                   - Recent developments that suggest consulting needs
                
                Analyze the additional requirements and tailor your searches to find companies 
                that specifically match these criteria. Generate and execute searches iteratively 
                to build a comprehensive list of potential clients that align with all specified requirements.""",
            ),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    filter_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"""You are an expert at analyzing and filtering potential clients. Review the search results and filter the most promising clients based on their size, industry, potential needs, and available contact information. 
                Focus on {current_year} data when available.
                
                Industry: {industry}
                Country: {country}
                Additional Requirements: {additional_requirements}""",
            ),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    finalizer_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"""You are an expert at presenting client information. Create a markdown table with the top 20 most promising clients from {current_year}.
        Include columns for:
        - Company Name
        - Industry
        - Location
        - Potential Needs
        - Contact Information (if available)
        - Website
        - Estimated Size
        - Recent News/Developments
        
        Format the output as a proper markdown document with a title and table.""",
            ),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    # Create the agents
    search_agent = create_tool_calling_agent(search_llm, tools, prompt=search_prompt)
    filter_agent = create_tool_calling_agent(filter_llm, tools, prompt=filter_prompt)
    finalizer_agent = create_tool_calling_agent(
        finalizer_llm, tools, prompt=finalizer_prompt
    )

    # Create agent executors
    search_executor = AgentExecutor(agent=search_agent, tools=tools, verbose=True)
    filter_executor = AgentExecutor(agent=filter_agent, tools=tools, verbose=True)
    finalizer_executor = AgentExecutor(agent=finalizer_agent, tools=tools, verbose=True)

    # Create leads directory if it doesn't exist
    leads_dir = "leads"
    if not os.path.exists(leads_dir):
        os.makedirs(leads_dir)

    # Generate filename with counter
    base_filename = f"{industry}_{country}"
    counter = 1
    while os.path.exists(
        os.path.join(leads_dir, f"leads_{base_filename}_{counter}.md")
    ):
        counter += 1
    filename = os.path.join(leads_dir, f"leads_{base_filename}_{counter}.md")

    # Step 1: Let the search agent find potential clients
    search_result = search_executor.invoke(
        {
            "input": f"""Find potential consulting clients in the {industry} industry from {country}.
            Focus on gathering comprehensive information about companies, including their websites,
            contact information, and recent developments."""
        }
    )
    
    # Process search results and get web content
    web_content = []
    if hasattr(search_tool, 'results') and search_tool.results:
        web_content = process_search_results(search_tool.results)
    
    web_content_context = "\n\n".join(web_content)

    # Step 2: Filter the results with additional context from web content
    filtered_results = filter_executor.invoke(
        {
            "input": f"""Filter these search results and web content to find the 20 most promising 
            and unique clients in {industry} industry from {country}, focusing on those with 
            available contact information:
            
            Search Results:
            {search_result['output']}
            
            Additional Web Content:
            {web_content_context}"""
        }
    )

    # Step 3: Create final presentation
    final_results = finalizer_executor.invoke(
        {
            "input": f"Create a detailed markdown table of the top 20 unique clients from {industry} industry in {country} from these results: {filtered_results['output']}"
        }
    )

    # Save results to a markdown file in the leads directory
    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_results["output"])

    # Return both the filename and the markdown table content
    return {"filename": filename, "table": final_results["output"]}


def process_search_results(search_results):
    """Extract URLs from search results and load their content"""
    urls = []
    # DuckDuckGo results come as a list of dictionaries with 'link', 'title', and 'snippet' keys
    for result in search_results:
        if isinstance(result, dict) and "link" in result:
            # Filter out non-http URLs and common file types we don't want to process
            url = result["link"]
            if url.startswith("http") and not any(
                ext in url.lower() for ext in [".pdf", ".doc", ".docx", ".ppt", ".pptx"]
            ):
                urls.append(url)

    if not urls:
        print("No valid URLs found in search results")
        return []

    print(f"Processing {len(urls)} URLs...")

    # Initialize WebBaseLoader with multiple URLs and custom headers
    loader = WebBaseLoader(
        urls,
        header_template={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )
    loader.requests_per_second = 2  # Be nice to servers

    try:
        # Load web content asynchronously
        docs = loader.aload()
        return [doc.page_content for doc in docs]
    except Exception as e:
        print(f"Error loading web content: {e}")
        return []


# Example usage
if __name__ == "__main__":
    industry = input("Enter the industry: ")
    country = input("Enter the country: ")
    additional_requirements = input(
        "Enter any additional requirements (press Enter if none): "
    )
    result = find_potential_clients(industry, country, additional_requirements)
    print(f"\nFinal Results have been saved to {os.path.basename(result['filename'])}")
    print("\nPreview of results:")
    print(result["table"])
