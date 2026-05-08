   
	
	
	  parameter ( ns = 50, np = 5000 )

	  real xn ( ns ), xp ( np ) , yp ( np )
	  integer kn ( ns ), kpol ( np , 2 ) , kp ( np ), matr(1500,1200)
      character*80 ch1 , ch2 , ch3 , ch4
      common / ch / ch3 , ch4
      open ( 24 , file = 'Polygon_project.txt' )
      read ( 24 , '(80a)' ) ch1
      read ( 24 , '(80a)' ) ch2
      read ( 24 , '(80a)' ) ch3
      read ( 24 , '(80a)' ) ch4
      
      open ( 16 , file = 't' )
	  open ( 8 , file = 't2.dat' )
	  open ( 7 , file = 'geom3.dat' )
      write(*,*) 'input file:', ch1
	  open ( 35 , file = ch1 )
      open ( 21 , file = ch2 )
      matr = 0
      read ( 35 , * ) dx , dy
      write(*,*) 'dx=', dx, 'dy=', dy
	  read ( 35 , * ) nnode
      
	  do i = 1 , nnode 
	    read ( 35 , * ) xp ( i ) , yp ( i )
      end do

	  read ( 35 , * ) nele
	  do i = 1 , nele    
	    read ( 35 , * ) kpol ( i , 1 ) , kpol ( i , 2 ) , kp ( i )
	  end do
	  write(*,*) nnode , nele
      nro = 0
	  nco = 0
	  xmin = 100000000.
	  ymin = xmin

	  xmax = - xmin
	  ymax = xmax

	  do i = 1 , nnode
	    x0 = xp ( i )
		y0 = yp ( i )
		if ( x0 .gt. xmax ) xmax = x0
		if ( x0 .lt. xmin ) xmin = x0		 
		if ( y0 .gt. ymax ) ymax = y0
		if ( y0 .lt. ymin ) ymin = y0
      end do

      xm0 = xmin - dx / 2. -0.012549
	  ym0 = ymin - dy / 2. - .05497

	  nx = int ( ( xmax + dx / 2. - xm0 ) / dx + .5 )
	  ny = int ( ( ymax + dy / 2. - ym0 ) / dy + .5 )
      write(*,*) 'nx=', nx, 'ny=', ny
      write(21,*) dx , dy
      write (21,*) nx , ny
      
	  do j = 1 , ny
	      y0 = ( j - 1 ) * dy + ym0 + dy / 2.
          icont = 0
         
	    do k = 1 , nele
	        k1 = kpol ( k , 1 )
	        k2 = kpol ( k , 2 )

           	x1 = xp ( k1 )
	        x2 = xp ( k2 )
          	y1 = yp ( k1 )
          	y2 = yp ( k2 )
        
	        yy1 = min ( y1 , y2 )
	        yy2 = max ( y1 , y2 )

	        if ( y0 .gt. yy1 .and. y0 .le. yy2 ) then
	            icont = icont + 1

 	            k0 = kp ( k )
                  r1 = ( y2 - y0 ) / ( y2 - y1 ) 
	            r2 = 1. - r1

	            x0 = r1 * x1 + r2 * x2
	            xn ( icont ) = x0
	            kn ( icont ) = k0
c                write(*,*) k1 , k2 , y0 , y1 , y2                
     
c                write(*,*) x0 , y0 , k0
c                pause
               end if 
	     end do
	     call sort ( icont , xn , kn )
           call rowcolx ( icont , xn , kn , j , dx , xm0 , matr , nro )
      end do


      do j = ny , 1 , -1
	    write(8 , '(200i2)' ) (matr ( i , j ),i=1 , nx)
      end do
c      matr = 0

	  do i = 1 , nx
	    x0 = ( i - 1 ) * dx + xm0 + dx / 2.
          icont = 0
	    do k = 1 , nele
	        k1 = kpol ( k , 1 )
	        k2 = kpol ( k , 2 )

             	x1 = xp ( k1 )
	        x2 = xp ( k2 )
          	y1 = yp ( k1 )
          	y2 = yp ( k2 )
              
	        xx1 = min ( x1 , x2 )
	        xx2 = max ( x1 , x2 )
	        if ( x0 .gt. xx1 .and. x0 .le. xx2 ) then
	            icont = icont + 1

	            k0 = kp ( k )
                  r1 = ( x2 - x0 ) / ( x2 - x1 ) 
	            r2 = 1. - r1

	            y0 = r1 * y1 + r2 * y2
	            xn ( icont ) = y0
	            kn ( icont ) = k0
               end if 
	     end do
	     call sort ( icont , xn , kn )
           call rowcoly ( icont , xn , kn , i , dy , ym0 , matr , nco)
      end do
      write(8,*)
      do j = ny , 1 , -1
	    write(8 , '(200i2)' ) (matr ( i , j ),i=1 , nx)
      end do		  
      
 

	  close (16)
	  open ( 16 , file = 't' )
	  write( 7 , * ) nro
      write( 21 , * ) nro
	  do i = 1 , nro
	     read ( 16 , * ) k1,k2,k3,k4,k5
	     write ( 7 , '(5i6)' ) k1,k2,k3,k4,k5
         write ( 21 , '(5i6)' ) k1,k2,k3,k4,k5
      end do
	  write( 7 , * ) nco
      write( 21 , * ) nco
	  do i = 1 , nco
	     read ( 16 , * ) k1,k2,k3,k4,k5
	     write ( 7 , '(5i6)' ) k1,k2,k3,k4,k5
         write ( 21 , '(5i6)' ) k1,k2,k3,k4,k5
      end do
      call plot ( nx , ny , dx , dy , xmin , ymin,  matr )
      close (7)
      close (21)
      end           

			     






c--------------------------------------------------------------------------
	  subroutine sort ( nn , xn , kn )
      parameter ( ns = 50 )

	  real xn ( ns )
	  integer kn ( ns )

      do i = 1 , nn-1
	    do j = 1 , nn - i
	       x1 = xn ( j )
	       x2 = xn ( j+1 )
	       k1 = kn ( j )
	       k2 = kn ( j+1 )
	       if ( x1 .gt. x2 ) then
	           xn ( j ) = x2
	           xn ( j+1 ) = x1
	           kn ( j ) = k2
	           kn ( j+1 ) = k1 
             end if
	    end do
	  end do
	  return
	  end		    
c----------------------------------------------------------------------------------
      subroutine rowcolx ( icont , xn , kn , j0 , dx , xm0 , matr , nro)
	        
      parameter ( ns = 50 )
       
	  real xn ( ns )
	  integer kn ( ns ) , matr ( 1500 , 1200 ) 
	
	  do i = 1 , icont , 2
	    x1 = xn ( i )
		x2 = xn ( i+1 )
		i1 = int ( ( x1 - xm0 - dx / 2. ) / dx  ) + 2
		i2 = int ( ( x2 - xm0 - dx / 2. ) / dx  ) +1
        if ( i2 .ge. i1 ) then
		write ( 16 , * ) i1 , i2 , j0 , kn ( i ) , kn ( i+1 )
	    nro = nro + 1
        write(*,*)x1 ,x2, xm0 , dx
        write(*,*) i1 , i2 , j0
        matr ( i1 , j0 ) = kn ( i )
		matr ( i2 , j0 ) = kn ( i+1 )
        end if
	    do k = i1+1 , i2-1
		     matr ( k , j0 ) = 1
	    end do
		  
	  end do
	  return
	  end
	
c----------------------------------------------------------------------------------
      subroutine rowcoly ( icont , xn , kn , j0 , dx , xm0 , matr , nro)
	        
      parameter ( ns = 50 )
       
	  real xn ( ns )
	  integer kn ( ns ) , matr ( 1500 , 1200 ) 
	
	  do i = 1 , icont , 2
	    x1 = xn ( i )
		x2 = xn ( i+1 )
		i1 = int ( ( x1 - xm0 - dx / 2. ) / dx  ) + 2
		i2 = int ( ( x2 - xm0 - dx / 2. ) / dx  ) +1
        if ( i2 .ge. i1 ) then
		write ( 16 , * ) i1 , i2 , j0 , kn ( i ) , kn ( i+1 )
	    nro = nro + 1
        matr ( j0 , i1 ) = kn ( i )
		matr ( j0 , i2 ) = kn ( i+1 )
        end if
	    do k = i1+1 , i2-1
	         m1 = matr ( j0 , k )
		     if ( m1 .lt. 2 ) matr ( j0 , k ) = 1
	    end do
		  
	  end do
	  return
	  end		 		 
c------------------------------------------------------------------------------
      subroutine plot ( nx , ny , dx , dy , xmin , ymin, matr  ) 
      integer matr ( 1500 , 1200 ) , matp ( 1500 , 1200 ) , 
     $              kele ( 400000 ,4)
      real xp ( 400000 ) , yp ( 400000 ) 
      integer Ike ( 400000 ) , Jke ( 400000 )
      common / ch / ch3 , ch4
      character* 80 ch3 , ch4       
      matp = 0
      open ( 11 , file = ch4 )
      
      write ( 11 , 10 )
      write ( 11 , 41 ) nx+1,ny+1
      
      do j = 1 , ny+1
          y = ymin + ( j-1.5 ) * dy
          do i = 1 , nx+1
              x = xmin + ( i-1.5 ) * dx
              write ( 11 , 22 ) x , y
          end do
      end do
      close ( 11 )        
              
      open ( 11 , file = ch3 )
      
      nnode = 0
      nelem = 0
      do i = 1 , nx
          do j = 1 , ny
              k0 = matr ( i , j )
              if ( k0 .gt. 0 ) then
                
                  nelem = nelem + 1
                  Ike ( nelem ) = i
                  Jke ( nelem ) = j
                  i0 = 0
                  do l1 = i , i+1
                      do l2 = j , j+1
                          i0 = i0 + 1
                          j0 = matp ( l1 , l2 )
                          if ( j0 .eq. 0 ) then
                              nnode = nnode + 1
                              matp ( l1 , l2 ) = nnode
                              j0 = nnode
                              xp ( j0 ) = xmin + ( l1-1.5 ) * dx
                              yp ( j0 ) = ymin + ( l2-1.5 ) * dy
                          end if
                          kele ( nelem , i0 ) = j0    
                      end do
                  end do
              end if
          end do
      end do            
      write ( 11 , 10 )
      write ( 11 , 11 ) nnode , nelem
      write ( 21 , * ) nnode , nelem
      
      write ( 7 , * ) nnode , nelem
      do i = 1 , nnode
          write ( 11 , 12 ) xp ( i ) , yp ( i )
          write ( 7 , 12 ) xp ( i ) , yp ( i )
          write ( 21 , 12 ) xp ( i ) , yp ( i )
      end do
      do i = 1 , nelem
          write ( 11 , 13 )  kele ( i , 1 ) , kele ( i , 2 ) , 
     $                       kele ( i , 4 ) , kele ( i , 3 )
          write ( 7 , 13 )  kele ( i , 1 ) , kele ( i , 2 ) , 
     $                       kele ( i , 4 ) , kele ( i , 3 )
          write ( 21 , 13 )  kele ( i , 1 ) , kele ( i , 2 ) , 
     $                       kele ( i , 4 ) , kele ( i , 3 ) ,
     $                        ike ( i ) , Jke ( i )    
      end do
      close ( 11 )

      rewind ( 7 )
      
      open ( 11 , file = ch4 )
      write ( 11 , 10 )
      read ( 7 , * ) nro
      do i = 1 , nro
          read ( 7 , * ) i1 , i2 , j0
          ix = i2 - i1 + 2
          iy = 2
          write ( 11 , 21 ) i , ix , iy
          do k = 1 , 2
              y = ymin + ( j0+k-2.5 ) * dy 
              do j = i1 , i2+1
                  x = xmin + ( j-1.5 ) * dx
                
                  write ( 11 , 22 ) x , y
              end do       
          end do
      end do
              
      read ( 7 , * ) nco
      do i = 1 , nco
          read ( 7 , * ) j1 , j2 , i0
          ix = 2
          iy = j2-j1+2
          write ( 11 , 31 ) i , iy , ix
          do k = 1 , 2
              x = xmin + ( i0+k-2.5 ) * dx 
              do j = j1 , j2+1
                  y = ymin + ( j-1.5 ) * dy
                
                  write ( 11 , 22 ) x , y
              end do       
          end do
      end do

      close (11)
10    format ( 'VARIABLES=X  Y' )
11    format ('ZONE T="main" N=',i6,' E=',i6,
     $            ' F=FEPOINT ET=QUADRILATERAL')
12    format ( 2f11.1 )
13    format ( 6i9 )
21    format ( 'ZONE T=" NRO ',i3,'" I=',i3,' J=',i3,' F=POINT' )
31    format ( 'ZONE T=" NCO ',i3,'" I=',i3,' J=',i3,' F=POINT' )
41    format ( 'ZONE T=" Main " I=',i3,' J=',i3,' F=POINT' )
22    format ( 2f11.4 ) 

      return
      end                                          
      