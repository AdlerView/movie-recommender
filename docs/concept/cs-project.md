  -------------------------------------------------------------------------------------
  App solves a problem        With access to thousands of movies and series across all
                              streaming platforms, it is easy to waste our time
                              searching for one that we would enjoy. This app is a
                              movie/series recommender which helps avoid aimless
                              scrolling
  --------------------------- ---------------------------------------------------------
  App uses data loaded via an We will use TMDB's API which is free and widely used.
  API/database                This is the API's documentation with a guide:
                              <https://developer.themoviedb.org/docs/getting-started>

  App visualizes data that    We could allow the users to consult their "stats" such as
  serves the use case         how many movies featuring X director or Y actor/actress.
                              Similar to Spotify wrapped but accessible anytime.

  App allows user interaction The idea was to allow the users to indicate a few
                              movies/series that they have watched and enjoyed, so that
                              we can get started with the recommendations. Each
                              recommendation can be interacted with by selecting a
                              "already watched" button in which case the user can give
                              a rating to the movie/series or a "not interested" button
                              which replaces the recommendation by another.

  App implements machine      I am not familiar with machine learning, but I'm pretty
  learning                    sure this can be implemented to support the movie
                              recommendation system.

  Source code is well         \-
  documented                  

  Team member contributions   \-
  are documented              

  4-minute video              \-
  -------------------------------------------------------------------------------------

**Requirements**

I'm leaving out all the design stuff on purpose because we can figure
this out later.\
Also I'm not really diving deep in everything but just theorizing the
way our app should be coded

1)  [This]{.mark} part requires a few things:\
    \
    A) we need to check how does TMDB categorizes/tags its movies\
    B) choose in accordance which tags we want to propose on the app\
    C) we need to figure out how to use the API in order to match the
    tags entered by the users to a movie from the database\
    C1) Since there will be many movies with the same tags, I'm thinking
    the simplest thing is to recommend movies from best to worse TMDB
    rating\
    C2) Once the users rates a movie, we need to remove it from the
    possible recommendations and stock it somewhere else so we can use
    its data for visualization and machine learning\
    D) After we match the movie with the user request, we need to
    retrieve it from the database to our page\
    E) (Details: like showing information from the movie, change the
    title of the page accordingly i.e. "You should watch: Batman")

2)  [The]{.mark} movies that have been rated can be considered as
    watched and we start using them in some infographics\
    \
    A) We need some kind of set to save all the rated movies so that we
    can access it for the visualization\
    B) We need to decide what info we want to show depending on what
    information is linked to the movies in the database (for instance if
    the movies are matched to their directors in TMDB we can show a stat
    showing the user's favorite director)

3)  [I don't]{.mark} know much about machine learning but I think our
    idea is a good use case for ML\
    \
    A) We need to save the ratings as well as the tags, actors,
    directors (we need to decide which factors we want to use depending
    on what is on TMDB) of the movies the user watched\
    B) Then based on which tags/actors/directors/... received the best
    ratings, we can search for similar movies in TMDB through their API\
    \
    We will probably know better after the ML class
